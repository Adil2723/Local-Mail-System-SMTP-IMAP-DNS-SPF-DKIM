#!/usr/bin/env python3
"""CN12 desktop demo. Host Tkinter UI; network operations run inside existing clients."""
import argparse
import json
import subprocess
import threading
import queue
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent
WORKER = r'''
import json, sys, ssl, smtplib, socket, imaplib, re, io, contextlib
from contextlib import ExitStack
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, make_msgid
from time import perf_counter
p = json.load(sys.stdin)
wire = sys.stdout
def emit(kind, **fields):
    print(json.dumps({'event':kind, **fields}), file=wire, flush=True)

def send():
    # Reuse the existing raw socket client's SMTP command/reply functions.
    ns = {'__name__': 'cn12_existing_client'}
    exec(compile(p['smtp_source'], 'smtp_client.py', 'exec'), ns)
    host, port = ns['HOST'], ns['PORT']
    msg = EmailMessage(policy=policy.SMTP)
    msg['From'] = ns['SENDER']; msg['To'] = 'adil@beta.lab'
    msg['Subject'] = p['subject']; msg['Date'] = formatdate()
    msg['Message-ID'] = make_msgid(domain='alpha.lab')
    msg.set_content(p['body'])
    data = re.sub(rb'(?m)^\.', b'..', msg.as_bytes())
    if not data.endswith(b'\r\n'): data += b'\r\n'
    transcript = io.StringIO(); tls_version = ''
    accepted = False
    warning = ''
    def stage(name, action):
        emit('stage', name=name, state='running')
        start=perf_counter(); offset=transcript.tell()
        try:
            action()
        except Exception as exc:
            emit('stage', name=name, state='failed', reply=str(exc))
            raise
        lines=transcript.getvalue()[offset:].splitlines()
        reply=next((line[3:] for line in reversed(lines) if line.startswith('S: ')), '')
        if name=='STARTTLS':
            reply=next((line for line in reversed(lines) if line.startswith('TLS: ')), reply)
        emit('stage', name=name, state='done', reply=reply, ms=(perf_counter()-start)*1000)
    with contextlib.redirect_stdout(transcript), ExitStack() as resources:
        emit('stage',name='CONNECT',state='running')
        start=perf_counter()
        try:
            conn = resources.enter_context(socket.create_connection((host, port), timeout=15))
            reader = resources.enter_context(conn.makefile('rb'))
            expect, command = ns['expect_reply'], ns['send_command']
            expect(reader, 220)
        except Exception as exc:
            emit('stage',name='CONNECT',state='failed',reply=str(exc)); raise
        emit('stage',name='CONNECT',state='done',reply=transcript.getvalue().splitlines()[-1][3:],ms=(perf_counter()-start)*1000)
        stage('EHLO', lambda: command(conn, reader, 'EHLO client-alpha.alpha.lab', 250))
        if p['tls']:
            def negotiate():
                nonlocal conn,reader,tls_version
                context=ssl.create_default_context(cafile=ns['CA_FILE'])
                started=perf_counter(); command(conn, reader, 'STARTTLS', 220); reader.close()
                conn=resources.enter_context(context.wrap_socket(conn,server_hostname=host))
                reader=resources.enter_context(conn.makefile('rb')); tls_version=conn.version()
                print(f'TLS: {tls_version} verified in {(perf_counter()-started)*1000:.2f} ms')
            stage('STARTTLS',negotiate)
            stage('EHLO (TLS)', lambda: command(conn, reader, 'EHLO client-alpha.alpha.lab', 250))
        stage('MAIL FROM', lambda: command(conn, reader, f'MAIL FROM:<{ns["SENDER"]}>',250))
        stage('RCPT TO', lambda: command(conn, reader, 'RCPT TO:<adil@beta.lab>',250,251))
        stage('DATA', lambda: command(conn,reader,'DATA',354))
        def submit():
            print('C: [message data]'); conn.sendall(data+b'.\r\n'); expect(reader,250)
        stage('MESSAGE ACCEPTANCE',submit); accepted=True
        try:
            stage('QUIT',lambda: command(conn,reader,'QUIT',221))
        except Exception as exc:
            warning='Message accepted; QUIT did not complete: '+str(exc)
    return {'id':str(msg['Message-ID']),'trace':transcript.getvalue(),'tls':tls_version,'accepted':accepted,'warning':warning}

def mailbox():
    with imaplib.IMAP4('10.10.2.10',143,timeout=20) as imap:
        try: imap.login('adil@beta.lab',p['password'])
        except imaplib.IMAP4.error: raise RuntimeError('IMAP login failed. Check your existing Adil mailbox password.') from None
        del p['password']
        status, count = imap.select('INBOX', readonly=True)
        if status != 'OK': raise RuntimeError('Could not open INBOX')
        if p['action']=='list':
            status, ids = imap.uid('search', None, 'ALL')
            if status != 'OK': raise RuntimeError('IMAP search failed')
            items=[]
            for uid in reversed(ids[0].split()[-30:]):
                status, parts=imap.uid('fetch',uid,'(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
                if status!='OK': continue
                raw=next((v[1] for v in parts if isinstance(v,tuple)),None)
                if raw is None: continue
                msg=BytesParser(policy=policy.default).parsebytes(raw)
                items.append({'uid':uid.decode(), 'subject':str(msg.get('Subject','(No subject)')), 'sender':str(msg.get('From','')), 'date':str(msg.get('Date',''))})
            return {'total':int(count[0]),'items':items}
        uid=p['uid']; assert uid.isdigit()
        status, parts=imap.uid('fetch',uid,'(BODY.PEEK[])')
        if status!='OK': raise RuntimeError('Could not fetch message')
        raw=next((v[1] for v in parts if isinstance(v,tuple)),None)
        if raw is None: raise RuntimeError('Message not found; refresh the inbox')
        msg=BytesParser(policy=policy.default).parsebytes(raw)
        part=msg.get_body(preferencelist=('plain',))
        body=part.get_content() if part is not None else '[No plain-text body available]'
        return {'subject':str(msg.get('Subject','')), 'sender':str(msg.get('From','')), 'to':str(msg.get('To','')), 'date':str(msg.get('Date','')), 'id':str(msg.get('Message-ID','')), 'spf':[str(x) for x in msg.get_all('Received-SPF',[])], 'auth':[str(x) for x in msg.get_all('Authentication-Results',[])], 'body':body}
try:
    result=send() if p['action']=='send' else mailbox()
    emit('result',ok=True,result=result)
except Exception as e:
    # Authentication errors are sanitized above. Do not echo the input JSON or password.
    emit('result',ok=False,error=str(e))
'''


def request(service,payload,on_stage=None):
    # Pass credentials/payload only on stdin, never in argv or files.
    args=[str(ROOT/'run-cn12.sh'),'exec','-T',service,'python3','-u','-c',WORKER]
    with tempfile.TemporaryFile(mode='w+t') as err:
        proc=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
        timer=threading.Timer(120,proc.kill); timer.daemon=True; timer.start()
        try:
            proc.stdin.write(json.dumps(payload)); proc.stdin.close()
            response=None
            for line in proc.stdout:
                try: event=json.loads(line)
                except ValueError: continue
                if event.get('event')=='stage' and on_stage: on_stage(event)
                elif event.get('event')=='result': response=event
            code=proc.wait()
            if code or response is None:
                raise RuntimeError('Docker client stopped or timed out. Check service status. If acceptance is uncertain, check the inbox before retrying.')
            if not response['ok']: raise RuntimeError(response['error'])
            return response['result']
        finally:
            timer.cancel()
            if proc.poll() is None: proc.kill(); proc.wait()
            proc.stdout.close()


PALETTES = {
 'light':dict(bg='#d8c6ed',panel='#f7f2fd',nav='#2e194c',header='#442267',fg='#21152f',muted='#71617e',navfg='#f5edff',navmuted='#bda9d5',line='#d7c9e8',field='#fffaff',accent='#783bd1',hover='#6529b4',selected='#e5d6fa',seltext='#4c247c',white='#ffffff',good='#217547',bad='#b52e45',row='#eee5f8'),
 'dark':dict(bg='#241734',panel='#30213f',nav='#20132f',header='#38204f',fg='#f3eaff',muted='#c4b3d4',navfg='#f5edff',navmuted='#ad98c7',line='#4d3863',field='#291b38',accent='#8e4de0',hover='#7935c6',selected='#523470',seltext='#ffffff',white='#ffffff',good='#9ce4b1',bad='#ff9aab',row='#3c2a4f'),
}
FONT = 'DejaVu Sans'

class App:
    def __init__(self, root, mode, theme='light'):
        self.root, self.mode, self.theme = root, mode, theme
        self.events=queue.Queue(); self.busy=False; self.items=[]; self.sent=[]; self.current=None
        self.widgets=[]; self.buttons=[]; self.progress=None; self.progress_rows={}; self.progress_states={}; self.last_steps=[]; self.status=tk.StringVar(value='Ready')
        self.search=tk.StringVar(); self.account='zaid@alpha.lab' if mode=='sender' else 'adil@beta.lab'
        root.title('CN Mail — '+('Zaid / Compose' if mode=='sender' else 'Adil / Inbox'))
        w=min(1280,root.winfo_screenwidth()-60); h=min(810,root.winfo_screenheight()-100)
        root.geometry(f'{w}x{h}+24+35'); root.minsize(min(780,w),min(510,h))
        self.style=ttk.Style(root); self.style.theme_use('clam')
        self.top=self.frame(root,'header'); self.top.pack(fill='x')
        self.logo=tk.Canvas(self.top,width=37,height=37,highlightthickness=0); self.logo.pack(side='left',padx=(18,7),pady=12)
        self.label(self.top,'CN Local Mail System' if w>=1000 else 'CN Mail',role='navfg',size=19 if w>=1000 else 17,bold=True).pack(side='left')
        self.label(self.top,'Sender' if mode=='sender' else 'Receiver',role='navmuted',size=10).pack(side='left',padx=14)
        self.theme_btn=ttk.Button(self.top,command=self.toggle_theme); self.theme_btn.pack(side='right',padx=(8,16),pady=10)
        self.label(self.top,self.account,role='navfg',size=10).pack(side='right',padx=8)
        self.rule(root).pack(fill='x')
        main=self.frame(root,'bg'); main.pack(fill='both',expand=True)
        self.nav=self.frame(main,'nav',width=194); self.nav.pack(side='left',fill='y'); self.nav.pack_propagate(False)
        self.label(self.nav,'CN MAIL',role='navfg',size=16,bold=True).pack(anchor='w',padx=18,pady=(24,3))
        self.label(self.nav,'Computer Networks',role='navmuted',size=10).pack(anchor='w',padx=18,pady=(0,22))
        def nav(text, action=None, primary=False):
            style='Accent.TButton' if primary else 'Nav.TButton'
            b=ttk.Button(self.nav,text=text,style=style,command=action)
            b.pack(fill='x',padx=12,pady=4)
            if action is None: b.configure(state='disabled')
            return b
        if mode=='sender':
            self.compose_btn=nav('✎  Compose',self.show_compose,True)
            nav('Inbox  ·  N/A')
            nav('➤  Send',self.send)
            nav('Sent this session',self.show_sent)
        else:
            nav('Compose  ·  N/A')
            nav('✉  Inbox',self.load,True)
            nav('Send  ·  N/A')
            nav('Refresh inbox',self.load)
        self.frame(self.nav,'line',height=1).pack(fill='x',padx=16,pady=18)
        self.label(self.nav,'OTHER FEATURES',role='navmuted',size=9,bold=True).pack(anchor='w',padx=18,pady=(0,7))
        for unused in range(2): nav('Not available')
        self.label(self.nav,'ACCOUNT',role='navmuted',size=9,bold=True).pack(anchor='w',padx=18,pady=(24,8))
        self.label(self.nav,'Zaid' if mode=='sender' else 'Adil',role='navfg',size=14,bold=True).pack(anchor='w',padx=18)
        self.label(self.nav,'Alpha domain' if mode=='sender' else 'Beta domain',role='navmuted').pack(anchor='w',padx=18,pady=4)
        self.label(self.nav,'SMTP / STARTTLS' if mode=='sender' else 'IMAP · read only',role='navmuted',size=9).pack(side='bottom',anchor='w',padx=18,pady=18)
        self.rule(main,vertical=True).pack(side='left',fill='y')
        self.content=self.frame(main,'panel'); self.content.pack(side='left',fill='both',expand=True,padx=12,pady=12)
        footer=self.frame(root,'panel'); footer.pack(side='bottom',fill='x'); self.rule(footer).pack(fill='x')
        self.label(footer,'●',role='muted',size=10).pack(side='left',padx=(16,7),pady=8)
        self.label(footer,variable=self.status,role='muted',size=10).pack(side='left',fill='x',expand=True)
        self.label(footer,'CN12  •  Local lab',role='muted',size=9).pack(side='right',padx=16)
        if mode=='sender': self.sender()
        else: self.receiver()
        self.apply_theme(); root.after(80,self.poll)
    def frame(self,parent,role='panel',**kwargs):
        w=tk.Frame(parent,bd=0,**kwargs); self.widgets.append((w,'frame',role)); return w
    def rule(self,parent,vertical=False):
        return self.frame(parent,'line',**({'width':1} if vertical else {'height':1}))
    def label(self,parent,text='',role='fg',size=11,bold=False,variable=None,**kwargs):
        w=tk.Label(parent,text=text,textvariable=variable,font=(FONT,size,'bold' if bold else 'normal'),bd=0,anchor='w',**kwargs)
        self.widgets.append((w,'label',role)); return w
    def text(self,parent,height=6,mono=False):
        w=tk.Text(parent,height=height,wrap='word',font=('DejaVu Sans Mono' if mono else FONT,10 if mono else 11),bd=0,relief='flat',highlightthickness=1,padx=12,pady=10,undo=True)
        self.widgets.append((w,'text','field')); return w
    def apply_theme(self):
        p=PALETTES[self.theme]; self.root.configure(bg=p['bg'])
        for w,kind,role in self.widgets:
            if not w.winfo_exists(): continue
            if kind=='frame': w.configure(bg=p[role])
            elif kind=='label': w.configure(bg=w.master.cget('bg'),fg=p[role])
            else: w.configure(bg=p['field'],fg=p['fg'],insertbackground=p['fg'],selectbackground=p['selected'],selectforeground=p['seltext'],highlightbackground=p['line'],highlightcolor=p['accent'])
        s=self.style
        s.configure('.',font=(FONT,10),background=p['panel'],foreground=p['fg'])
        s.configure('TButton',padding=(10,8),background=p['field'],foreground=p['fg'],bordercolor=p['line'],lightcolor=p['field'],darkcolor=p['field'],relief='flat')
        s.map('TButton',background=[('active',p['selected'])],foreground=[('disabled',p['muted'])])
        s.configure('Accent.TButton',background=p['accent'],foreground=p['white'],padding=(13,9),bordercolor=p['accent'],lightcolor=p['accent'],darkcolor=p['accent'],font=(FONT,10,'bold'))
        s.map('Accent.TButton',background=[('disabled',p['line']),('active',p['hover'])],foreground=[('disabled',p['muted'])])
        s.configure('Nav.TButton',background=p['nav'],foreground=p['navfg'],padding=(9,10),bordercolor=p['nav'],lightcolor=p['nav'],darkcolor=p['nav'],anchor='w'); s.map('Nav.TButton',background=[('active',p['header']),('disabled',p['nav'])],foreground=[('disabled',p['navmuted'])])
        s.configure('SMTP.Horizontal.TProgressbar',background=p['accent'],troughcolor=p['line'],bordercolor=p['line'],lightcolor=p['accent'],darkcolor=p['accent'],thickness=9)
        s.configure('TEntry',padding=8,fieldbackground=p['field'],foreground=p['fg'],insertcolor=p['fg'],bordercolor=p['line'],lightcolor=p['line'],darkcolor=p['line'])
        s.configure('TCheckbutton',background=p['panel'],foreground=p['fg']); s.map('TCheckbutton',background=[('active',p['panel'])],foreground=[('active',p['fg'])])
        s.configure('Treeview',background=p['panel'],fieldbackground=p['panel'],foreground=p['fg'],rowheight=34,borderwidth=0,font=(FONT,10))
        s.configure('Treeview.Heading',background=p['field'],foreground=p['muted'],padding=7,relief='flat'); s.map('Treeview',background=[('selected',p['selected'])],foreground=[('selected',p['seltext'])])
        s.configure('Vertical.TScrollbar',background=p['line'],troughcolor=p['panel'],bordercolor=p['panel'],arrowcolor=p['muted'])
        self.logo.configure(bg=p['header']); self.logo.delete('all'); self.logo.create_rectangle(4,6,33,31,fill=p['accent'],outline=''); self.logo.create_line(5,8,18.5,20,32,8,fill='white',width=2.5,joinstyle='round'); self.logo.create_line(5,29,14,18,fill='white',width=1.5); self.logo.create_line(32,29,23,18,fill='white',width=1.5)
        self.theme_btn.configure(text='Dark mode' if self.theme=='light' else 'Light mode')
        if hasattr(self,'panes'): self.panes.configure(bg=p['line'])
        if self.progress and self.progress.winfo_exists():
            self.progress.configure(bg=p['bg'])
            self.paint_progress()
    def toggle_theme(self):
        self.theme='dark' if self.theme=='light' else 'light'; self.apply_theme()
    def sender(self):
        self.compose=self.frame(self.content); self.compose.pack(fill='both',expand=True,padx=22,pady=15)
        title=self.frame(self.compose); title.pack(fill='x')
        self.label(title,'Compose Message',size=20,bold=True).pack(side='left')
        ttk.Button(title,text='Clear',command=self.clear).pack(side='right')
        self.rule(self.compose).pack(fill='x',pady=(12,3))
        for key,val in [('From','zaid@alpha.lab'),('To','adil@beta.lab')]:
            row=self.frame(self.compose); row.pack(fill='x',pady=4)
            self.label(row,key,width=8,role='muted').pack(side='left'); self.label(row,val,bold=(key=='To')).pack(side='left')
            self.rule(self.compose).pack(fill='x',pady=3)
        self.label(self.compose,'Subject',role='muted',size=10).pack(anchor='w',pady=(7,4))
        self.subject=ttk.Entry(self.compose); self.subject.pack(fill='x')
        self.label(self.compose,'Message',role='muted',size=10).pack(anchor='w',pady=(10,4))
        self.body=self.text(self.compose,7); self.body.pack(fill='both',expand=True)
        actions=self.frame(self.compose); actions.pack(fill='x',pady=12)
        self.send_btn=ttk.Button(actions,text='Send Message',style='Accent.TButton',command=self.send); self.send_btn.pack(side='left')
        self.tls=tk.BooleanVar(value=True); ttk.Checkbutton(actions,text='STARTTLS',variable=self.tls).pack(side='left',padx=14)
        ttk.Button(actions,text='Protocol details',command=self.show_trace).pack(side='right')
        self.last_trace='No message sent yet.'; self.buttons=[self.send_btn]
        self.history=self.frame(self.content)
        self.label(self.history,'Sent this session',size=20,bold=True).pack(anchor='w',padx=22,pady=18)
        self.history_text=self.text(self.history,10); self.history_text.pack(fill='both',expand=True,padx=22,pady=(0,18)); self.show(self.history_text,'No messages sent in this session.')
    def clear(self):
        if self.busy: return
        self.subject.delete(0,'end'); self.body.delete('1.0','end')
    def show_compose(self):
        self.history.pack_forget(); self.compose.pack(fill='both',expand=True,padx=22,pady=15)
    def show_sent(self):
        self.compose.pack_forget(); self.history.pack(fill='both',expand=True)
        self.show(self.history_text,'\n\n'.join(self.sent) or 'No messages sent in this session.')
    def show_trace(self):
        win=tk.Toplevel(self.root); win.title('CN Mail — SMTP protocol details'); win.geometry('720x440')
        frame=self.frame(win); frame.pack(fill='both',expand=True,padx=12,pady=12)
        w=self.text(frame,12,True); w.pack(fill='both',expand=True); self.show(w,self.last_trace)
        self.apply_theme()
    def receiver(self):
        bar=self.frame(self.content); bar.pack(fill='x',padx=15,pady=(14,8))
        self.label(bar,'Mailbox password',role='muted',size=10).pack(side='left',padx=(0,8))
        self.password=ttk.Entry(bar,show='•',width=20); self.password.pack(side='left',fill='x',expand=True)
        self.refresh=ttk.Button(bar,text='Refresh',style='Accent.TButton',command=self.load); self.refresh.pack(side='left',padx=(8,0))
        self.password.bind('<Return>',lambda e:self.load())
        self.rule(self.content).pack(fill='x')
        self.panes=tk.PanedWindow(self.content,orient='horizontal',sashwidth=5,bd=0,relief='flat'); self.panes.pack(fill='both',expand=True)
        inbox=self.frame(self.panes); reading=self.frame(self.panes); self.panes.add(inbox,minsize=210,width=350); self.panes.add(reading,minsize=250)
        self.label(inbox,'Inbox',size=19,bold=True).pack(anchor='w',padx=12,pady=(14,4))
        self.count=tk.StringVar(value='Connect to your mailbox'); self.label(inbox,variable=self.count,role='muted',size=9).pack(anchor='w',padx=12,pady=(0,9))
        self.label(inbox,'Search recent mail',role='muted',size=9).pack(anchor='w',padx=12)
        ttk.Entry(inbox,textvariable=self.search).pack(fill='x',padx=12,pady=(3,10)); self.search.trace_add('write',lambda *a:self.populate())
        holder=self.frame(inbox); holder.pack(fill='both',expand=True,padx=6,pady=(0,8))
        self.tree=ttk.Treeview(holder,columns=('sender','subject'),show='headings',selectmode='browse'); self.tree.heading('sender',text='From'); self.tree.heading('subject',text='Subject'); self.tree.column('sender',width=145,minwidth=85,stretch=True); self.tree.column('subject',width=190,minwidth=90,stretch=True); self.tree.pack(side='left',fill='both',expand=True)
        sb=ttk.Scrollbar(holder,orient='vertical',command=self.tree.yview); sb.pack(side='right',fill='y'); self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind('<Double-1>',lambda e:self.read()); self.tree.bind('<Return>',lambda e:self.read())
        self.open_btn=ttk.Button(inbox,text='Open message',command=self.read); self.open_btn.pack(fill='x',padx=12,pady=(0,12))
        head=self.frame(reading); head.pack(fill='x',padx=18,pady=(15,10))
        self.label(head,'Message',size=19,bold=True).pack(side='left'); ttk.Button(head,text='Details',command=self.details).pack(side='right')
        self.rule(reading).pack(fill='x',padx=18)
        self.subject_line=tk.StringVar(value='Select a message'); self.label(reading,variable=self.subject_line,size=15,bold=True,wraplength=390,justify='left').pack(anchor='w',padx=18,pady=(14,8))
        self.from_line=tk.StringVar(value=''); self.label(reading,variable=self.from_line,role='muted',size=10,wraplength=390,justify='left').pack(anchor='w',padx=18)
        self.auth_line=tk.StringVar(value=''); self.label(reading,variable=self.auth_line,role='muted',size=10,wraplength=390,justify='left').pack(anchor='w',padx=18,pady=8)
        self.preview=self.text(reading,10); self.preview.pack(fill='both',expand=True,padx=18,pady=(5,15)); self.show(self.preview,'Refresh the inbox, then open a message to read it here.')
        self.buttons=[self.refresh,self.open_btn]
    def populate(self):
        if not hasattr(self,'tree'): return
        term=self.search.get().strip().casefold(); self.tree.delete(*self.tree.get_children())
        for item in self.items:
            if term not in (item['sender']+' '+item['subject']).casefold(): continue
            sender=item['sender'].split('<')[0].strip(' "') or item['sender']; self.tree.insert('','end',iid=item['uid'],values=(sender,item['subject']))
    def details(self):
        if not self.current: return
        r=self.current; win=tk.Toplevel(self.root); win.title('CN Mail — Message details'); win.geometry('680x460')
        frame=self.frame(win); frame.pack(fill='both',expand=True,padx=12,pady=12); w=self.text(frame,14,True); w.pack(fill='both',expand=True)
        self.show(w,'\n'.join([f"Message-ID: {r['id']}",f"Date: {r['date']}",f"To: {r['to']}",'',*r['spf'],*r['auth']])); self.apply_theme()
    def show(self,w,text):
        w.configure(state='normal'); w.delete('1.0','end'); w.insert('1.0',text); w.configure(state='disabled')
    def start(self,service,payload,callback):
        if self.busy: return
        self.busy=True; self.status.set('Working…')
        for b in self.buttons: b.configure(state='disabled')
        def work():
            try: self.events.put(('result',callback,request(service,payload,lambda event:self.events.put(('stage',event))),None))
            except Exception as e: self.events.put(('result',callback,None,str(e)))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        try:
            # Drain all pending events; each status is based on a real reply.
            while True:
                item=self.events.get_nowait()
                if item[0]=='stage':
                    self.update_progress(item[1]); continue
                _,callback,result,error=item; self.busy=False
                for b in self.buttons: b.configure(state='normal')
                if error:
                    self.status.set('Operation failed')
                    if self.mode=='sender' and self.progress and self.progress.winfo_exists():
                        self.finish_progress(None,error)
                    else: messagebox.showerror('CN Mail',error,parent=self.root)
                else: callback(result)
        except queue.Empty: pass
        self.root.after(50,self.poll)
    def open_progress(self,tls):
        if self.progress and self.progress.winfo_exists(): self.progress.destroy()
        self.progress_states={}; self.progress_rows={}; self.last_steps=[]
        stages=['CONNECT','EHLO']+(['STARTTLS','EHLO (TLS)'] if tls else [])+['MAIL FROM','RCPT TO','DATA','MESSAGE ACCEPTANCE','QUIT']
        win=tk.Toplevel(self.root); self.progress=win; win.title('CN Mail — SMTP transaction progress'); win.transient(self.root)
        width=min(610,self.root.winfo_screenwidth()-36); height=min(690,self.root.winfo_screenheight()-85)
        win.geometry(f'{width}x{height}+{max(0,self.root.winfo_rootx()+self.root.winfo_width()//2-width//2)}+{max(0,self.root.winfo_rooty()+self.root.winfo_height()//2-height//2)}')
        win.protocol('WM_DELETE_WINDOW',lambda:None if self.busy else win.destroy())
        top=self.frame(win,'header'); top.pack(fill='x')
        self.label(top,'➤  SMTP Transaction Progress',role='navfg',size=16,bold=True).pack(anchor='w',padx=18,pady=(13,3))
        self.progress_caption=tk.StringVar(value='Sending message • real server responses')
        self.label(top,variable=self.progress_caption,role='navmuted',size=10).pack(anchor='w',padx=18,pady=(0,13))
        area=self.frame(win,'panel'); area.pack(fill='both',expand=True,padx=10,pady=10)
        # Compact rows adapt to the nine real transaction stages.
        rows=self.frame(area,'panel'); rows.pack(fill='both',expand=True,padx=10,pady=8)
        for stage in stages:
            line=self.frame(rows,'row'); line.pack(fill='both',expand=True,pady=2)
            status=tk.Label(line,text='○',font=(FONT,14,'bold'),width=2,bd=0); status.pack(side='left',padx=(7,2))
            label=self.label(line,stage,size=10,bold=True); label.pack(side='left',padx=3)
            value=tk.Label(line,text='Waiting',font=(FONT,9),anchor='e',justify='right',wraplength=max(150,width-265)); value.pack(side='right',fill='x',expand=True,padx=(4,9))
            self.progress_rows[stage]=(line,status,value)
            self.progress_states[stage]={'state':'waiting'}
        footer=self.frame(area); footer.pack(fill='x',padx=10,pady=(0,9))
        self.bar=ttk.Progressbar(footer,style='SMTP.Horizontal.TProgressbar',maximum=len(stages),mode='determinate'); self.bar.pack(fill='x')
        self.progress_count=tk.StringVar(value=f'0 / {len(stages)} stages confirmed'); self.label(footer,variable=self.progress_count,role='muted',size=9).pack(anchor='w',pady=5)
        self.security_line=tk.StringVar(value=('STARTTLS requested' if tls else 'Plaintext SMTP')+' · SPF/DKIM: verify in receiver')
        self.label(footer,variable=self.security_line,role='muted',size=9,wraplength=width-65,justify='left').pack(anchor='w',pady=4)
        self.close_progress=ttk.Button(footer,text='Close',command=win.destroy,state='disabled'); self.close_progress.pack(side='right',pady=3)
        self.apply_theme()
    def paint_progress(self):
        p=PALETTES[self.theme]
        for name,(line,status,value) in self.progress_rows.items():
            e=self.progress_states[name]; state=e['state']; symbol={'waiting':'○','running':'◔','done':'✓','failed':'×'}[state]; color={'waiting':p['muted'],'running':p['accent'],'done':p['good'],'failed':p['bad']}[state]
            status.configure(text=symbol,bg=p['row'],fg=color)
            result=e.get('reply','')
            if state=='done': result=(result or 'Confirmed')+f"  ·  {e['ms']:.2f} ms"
            elif state=='running': result='In progress…'
            elif state=='waiting': result='Waiting'
            value.configure(text=result,bg=p['row'],fg=color)
    def update_progress(self,event):
        name=event['name']
        if name not in self.progress_states: return
        self.progress_states[name]=event
        if event['state'] in ('done','failed'): self.last_steps.append(event.copy())
        if not self.progress or not self.progress.winfo_exists(): return
        count=sum(e['state']=='done' for e in self.progress_states.values()); self.bar['value']=count
        self.progress_count.set(f'{count} / {len(self.progress_states)} stages confirmed')
        if name=='STARTTLS' and event['state']=='done': self.security_line.set('STARTTLS certificate verified · SPF/DKIM: verify in receiver')
        self.paint_progress()
    def finish_progress(self,result,error=None):
        if not self.progress or not self.progress.winfo_exists(): return
        if error:
            accepted=self.progress_states.get('MESSAGE ACCEPTANCE',{}).get('state')=='done'
            self.progress_caption.set('Accepted by SMTP; later operation failed' if accepted else 'Transaction failed or acceptance unconfirmed')
            self.security_line.set(error[:250])
        else:
            self.progress_caption.set('Message accepted by SMTP server' if not result.get('warning') else 'Accepted • QUIT warning')
            self.security_line.set((result.get('warning') or ('Transport: '+(result['tls'] or 'Plaintext')+' · SPF/DKIM: verify in receiver'))[:250])
        self.close_progress.configure(state='normal'); self.paint_progress()
    def send(self):
        if self.busy: return
        self.show_compose()
        subject=self.subject.get().strip(); body=self.body.get('1.0','end-1c')
        if not subject or not body.strip(): messagebox.showwarning('CN Mail','Enter a subject and message.',parent=self.root); return
        try: source=(ROOT/'smtp_client.py').read_text()
        except OSError: messagebox.showerror('CN Mail','smtp_client.py not found in project folder.',parent=self.root); return
        def done(r):
            self.finish_progress(r); self.last_trace=r['trace']; self.sent.insert(0,f"{subject}\nTo: adil@beta.lab\nSMTP accepted · {r['id']}\n{body}"); self.status.set('Message accepted by SMTP server')
            if self.subject.get().strip()==subject and self.body.get('1.0','end-1c')==body: self.clear()
            self.show(self.history_text,'\n\n'.join(self.sent))
        self.open_progress(self.tls.get())
        self.start('client-alpha',{'action':'send','subject':subject,'body':body,'tls':self.tls.get(),'smtp_source':source},done)
    def load(self):
        password=self.password.get()
        if not password: messagebox.showwarning('CN Mail','Enter your existing Adil IMAP password.',parent=self.root); return
        def done(r):
            self.items=r['items']; self.populate(); self.count.set(f"{r['total']:,} messages · latest {len(self.items)}"); self.status.set('Inbox refreshed via IMAP · read-only')
        self.start('client-beta',{'action':'list','password':password},done)
    def read(self):
        selection=self.tree.selection()
        if not selection or not self.password.get(): return
        def done(r):
            import re
            self.current=r; self.subject_line.set(r['subject'] or '(No subject)'); self.from_line.set('From: '+r['sender']+'\nTo: '+r['to']+'\n'+r['date'])
            spf=next((m.group(1).upper() for h in r['spf'] if (m:=re.match(r'^\s*(\w+)',h))), 'Not recorded')
            dkim=next((m.group(1).upper() for h in r['auth'] if (m:=re.search(r'\bdkim=([\w-]+)',h,re.I))), 'Not recorded')
            self.auth_line.set(f'SPF: {spf}    ·    DKIM: {dkim}'); self.show(self.preview,r['body']); self.status.set('Message retrieved via IMAP (read-only)')
        self.start('client-beta',{'action':'read','password':self.password.get(),'uid':selection[0]},done)

def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['sender','receiver']); p.add_argument('--theme',choices=['light','dark'],default='light'); a=p.parse_args(); root=tk.Tk(); App(root,a.mode,a.theme); root.mainloop()
if __name__=='__main__': main()
