#!/usr/bin/env python3
"""CN12 desktop demo. Host Tkinter UI; network operations run inside existing clients."""
import argparse
import json
import subprocess
import threading
import queue
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
    with contextlib.redirect_stdout(transcript), ExitStack() as resources:
        conn = resources.enter_context(socket.create_connection((host, port), timeout=15))
        reader = resources.enter_context(conn.makefile('rb'))
        expect, command = ns['expect_reply'], ns['send_command']
        expect(reader, 220); command(conn, reader, 'EHLO client-alpha.alpha.lab', 250)
        if p['tls']:
            context = ssl.create_default_context(cafile=ns['CA_FILE'])
            started = perf_counter(); command(conn, reader, 'STARTTLS', 220); reader.close()
            conn = resources.enter_context(context.wrap_socket(conn, server_hostname=host))
            reader = resources.enter_context(conn.makefile('rb'))
            tls_version = conn.version()
            print(f'TLS: {tls_version} verified in {(perf_counter()-started)*1000:.2f} ms')
            command(conn, reader, 'EHLO client-alpha.alpha.lab', 250)
        command(conn, reader, f'MAIL FROM:<{ns["SENDER"]}>', 250)
        command(conn, reader, 'RCPT TO:<adil@beta.lab>', 250, 251)
        command(conn, reader, 'DATA', 354)
        print('C: [message data]'); conn.sendall(data + b'.\r\n'); expect(reader, 250)
        command(conn, reader, 'QUIT', 221)
    return {'id': str(msg['Message-ID']), 'trace': transcript.getvalue(), 'tls': tls_version}

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
    print(json.dumps({'ok':True,'result':result}))
except Exception as e:
    # Authentication errors are sanitized above. Do not echo the input JSON or password.
    print(json.dumps({'ok':False,'error':str(e)}))
'''


def request(service, payload):
    proc = subprocess.run([str(ROOT/'run-cn12.sh'),'exec','-T',service,'python3','-c',WORKER], cwd=ROOT, input=json.dumps(payload), text=True, capture_output=True, timeout=90)
    if proc.returncode: raise RuntimeError('Docker operation failed. Check that the project services are running.\n'+proc.stderr[-1200:])
    try: response=json.loads(proc.stdout)
    except ValueError: raise RuntimeError('Invalid response from Docker client. Check service status.') from None
    if not response['ok']: raise RuntimeError(response['error'])
    return response['result']

PALETTES = {
    'light': dict(bg='#f4f2f8', panel='#ffffff', nav='#f5f3fa', fg='#252237', muted='#706a80', line='#e5e0ed', field='#faf9fc', accent='#7654c5', hover='#6541b5', selected='#e9e1fa', seltext='#4f318f', white='#ffffff', good='#28764c'),
    'dark': dict(bg='#1c1925', panel='#252131', nav='#201c2b', fg='#eeeaf7', muted='#b4a9c5', line='#3b344a', field='#2c263a', accent='#8b69d4', hover='#7857c4', selected='#44335e', seltext='#f1e6ff', white='#ffffff', good='#8bd3a8'),
}
FONT = 'DejaVu Sans'

class App:
    def __init__(self, root, mode, theme='light'):
        self.root, self.mode, self.theme = root, mode, theme
        self.events=queue.Queue(); self.busy=False; self.items=[]; self.sent=[]; self.current=None
        self.widgets=[]; self.buttons=[]; self.status=tk.StringVar(value='Ready')
        self.search=tk.StringVar(); self.account='zaid@alpha.lab' if mode=='sender' else 'adil@beta.lab'
        root.title('CN Mail — '+('Zaid / Compose' if mode=='sender' else 'Adil / Inbox'))
        w=min(1120,root.winfo_screenwidth()-60); h=min(730,root.winfo_screenheight()-100)
        root.geometry(f'{w}x{h}+24+35'); root.minsize(min(780,w),min(510,h))
        self.style=ttk.Style(root); self.style.theme_use('clam')
        self.top=self.frame(root,'panel'); self.top.pack(fill='x')
        self.logo=tk.Canvas(self.top,width=37,height=37,highlightthickness=0); self.logo.pack(side='left',padx=(18,7),pady=12)
        self.label(self.top,'CN Mail',size=19,bold=True).pack(side='left')
        self.label(self.top,'Local mail',role='muted',size=10).pack(side='left',padx=14)
        self.theme_btn=ttk.Button(self.top,command=self.toggle_theme); self.theme_btn.pack(side='right',padx=(8,16),pady=10)
        self.label(self.top,self.account,role='muted',size=10).pack(side='right',padx=8)
        self.rule(root).pack(fill='x')
        main=self.frame(root,'bg'); main.pack(fill='both',expand=True)
        self.nav=self.frame(main,'nav',width=168); self.nav.pack(side='left',fill='y'); self.nav.pack_propagate(False)
        self.label(self.nav,'WORKSPACE',role='muted',size=9,bold=True).pack(anchor='w',padx=18,pady=(22,10))
        if mode=='sender':
            self.compose_btn=ttk.Button(self.nav,text='＋  Compose',style='Accent.TButton',command=self.show_compose); self.compose_btn.pack(fill='x',padx=12,pady=(0,12))
            ttk.Button(self.nav,text='Sent this session',command=self.show_sent).pack(fill='x',padx=12,pady=3)
        else:
            ttk.Button(self.nav,text='Inbox',style='Accent.TButton',command=self.load).pack(fill='x',padx=12,pady=(0,12))
            ttk.Button(self.nav,text='Refresh inbox',command=self.load).pack(fill='x',padx=12,pady=3)
        self.label(self.nav,'ACCOUNT',role='muted',size=9,bold=True).pack(anchor='w',padx=18,pady=(28,8))
        self.label(self.nav,'Zaid' if mode=='sender' else 'Adil',size=13,bold=True).pack(anchor='w',padx=18)
        self.label(self.nav,'Alpha domain' if mode=='sender' else 'Beta domain',role='muted').pack(anchor='w',padx=18,pady=4)
        self.label(self.nav,'SMTP / STARTTLS' if mode=='sender' else 'IMAP · read only',role='muted',size=9).pack(side='bottom',anchor='w',padx=18,pady=18)
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
        s.configure('TEntry',padding=8,fieldbackground=p['field'],foreground=p['fg'],insertcolor=p['fg'],bordercolor=p['line'],lightcolor=p['line'],darkcolor=p['line'])
        s.configure('TCheckbutton',background=p['panel'],foreground=p['fg']); s.map('TCheckbutton',background=[('active',p['panel'])],foreground=[('active',p['fg'])])
        s.configure('Treeview',background=p['panel'],fieldbackground=p['panel'],foreground=p['fg'],rowheight=34,borderwidth=0,font=(FONT,10))
        s.configure('Treeview.Heading',background=p['field'],foreground=p['muted'],padding=7,relief='flat'); s.map('Treeview',background=[('selected',p['selected'])],foreground=[('selected',p['seltext'])])
        s.configure('Vertical.TScrollbar',background=p['line'],troughcolor=p['panel'],bordercolor=p['panel'],arrowcolor=p['muted'])
        self.logo.configure(bg=p['panel']); self.logo.delete('all'); self.logo.create_rectangle(4,6,33,31,fill=p['accent'],outline=''); self.logo.create_line(5,8,18.5,20,32,8,fill='white',width=2.5,joinstyle='round'); self.logo.create_line(5,29,14,18,fill='white',width=1.5); self.logo.create_line(32,29,23,18,fill='white',width=1.5)
        self.theme_btn.configure(text='Dark mode' if self.theme=='light' else 'Light mode')
        if hasattr(self,'panes'): self.panes.configure(bg=p['line'])
    def toggle_theme(self):
        self.theme='dark' if self.theme=='light' else 'light'; self.apply_theme()
    def sender(self):
        self.compose=self.frame(self.content); self.compose.pack(fill='both',expand=True,padx=22,pady=15)
        title=self.frame(self.compose); title.pack(fill='x')
        self.label(title,'New message',size=20,bold=True).pack(side='left')
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
        self.send_btn=ttk.Button(actions,text='Send',style='Accent.TButton',command=self.send); self.send_btn.pack(side='left')
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
        inbox=self.frame(self.panes); reading=self.frame(self.panes); self.panes.add(inbox,minsize=210,width=310); self.panes.add(reading,minsize=250)
        self.label(inbox,'Inbox',size=19,bold=True).pack(anchor='w',padx=12,pady=(14,4))
        self.count=tk.StringVar(value='Connect to your mailbox'); self.label(inbox,variable=self.count,role='muted',size=9).pack(anchor='w',padx=12,pady=(0,9))
        self.label(inbox,'Search recent mail',role='muted',size=9).pack(anchor='w',padx=12)
        ttk.Entry(inbox,textvariable=self.search).pack(fill='x',padx=12,pady=(3,10)); self.search.trace_add('write',lambda *a:self.populate())
        holder=self.frame(inbox); holder.pack(fill='both',expand=True,padx=6,pady=(0,8))
        self.tree=ttk.Treeview(holder,columns=('sender','subject'),show='headings',selectmode='browse'); self.tree.heading('sender',text='From'); self.tree.heading('subject',text='Subject'); self.tree.column('sender',width=95,minwidth=65,stretch=True); self.tree.column('subject',width=190,minwidth=90,stretch=True); self.tree.pack(side='left',fill='both',expand=True)
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
            try: self.events.put((callback,request(service,payload),None))
            except Exception as e: self.events.put((callback,None,str(e)))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        try:
            callback,result,error=self.events.get_nowait(); self.busy=False
            for b in self.buttons: b.configure(state='normal')
            if error: self.status.set('Operation failed'); messagebox.showerror('CN Mail',error,parent=self.root)
            else: callback(result)
        except queue.Empty: pass
        self.root.after(80,self.poll)
    def send(self):
        subject=self.subject.get().strip(); body=self.body.get('1.0','end-1c')
        if not subject or not body.strip(): messagebox.showwarning('CN Mail','Enter a subject and message.',parent=self.root); return
        try: source=(ROOT/'smtp_client.py').read_text()
        except OSError: messagebox.showerror('CN Mail','smtp_client.py not found in project folder.',parent=self.root); return
        def done(r):
            self.last_trace=r['trace']; self.sent.insert(0,f"{subject}\nTo: adil@beta.lab\nSMTP accepted · {r['id']}\n{body}"); self.status.set('Message accepted by SMTP server')
            if self.subject.get().strip()==subject and self.body.get('1.0','end-1c')==body: self.clear()
            self.show(self.history_text,'\n\n'.join(self.sent))
        self.start('client-alpha',{'action':'send','subject':subject,'body':body,'tls':self.tls.get(),'smtp_source':source},done)
    def load(self):
        password=self.password.get()
        if not password: messagebox.showwarning('CN Mail','Enter your existing Adil IMAP password.',parent=self.root); return
        def done(r):
            self.items=r['items']; self.populate(); self.count.set(f"{r['total']:,} messages · latest {len(self.items)}"); self.status.set('Inbox refreshed via IMAP')
        self.start('client-beta',{'action':'list','password':password},done)
    def read(self):
        selection=self.tree.selection()
        if not selection or not self.password.get(): return
        def done(r):
            import re
            self.current=r; self.subject_line.set(r['subject'] or '(No subject)'); self.from_line.set(r['sender']+'\n'+r['date'])
            spf=next((m.group(1).upper() for h in r['spf'] if (m:=re.match(r'^\s*(\w+)',h))), 'Not recorded')
            dkim=next((m.group(1).upper() for h in r['auth'] if (m:=re.search(r'\bdkim=([\w-]+)',h,re.I))), 'Not recorded')
            self.auth_line.set(f'SPF: {spf}    ·    DKIM: {dkim}'); self.show(self.preview,r['body']); self.status.set('Message retrieved via IMAP (read-only)')
        self.start('client-beta',{'action':'read','password':self.password.get(),'uid':selection[0]},done)

def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['sender','receiver']); p.add_argument('--theme',choices=['light','dark'],default='light'); a=p.parse_args(); root=tk.Tk(); App(root,a.mode,a.theme); root.mainloop()
if __name__=='__main__': main()
