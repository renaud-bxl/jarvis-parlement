"""Readable mail bodies and isolated HTML rendering without remote resources."""
import base64,re
from html import escape
from html.parser import HTMLParser

class CleanHTML(HTMLParser):
    tags=set('p div span br hr b strong i em u s blockquote pre code ul ol li h1 h2 h3 h4 h5 h6 table thead tbody tfoot tr td th caption a img'.split())
    blocked=set('script style iframe object embed form button input textarea select svg math head title'.split())
    void={'br','hr','img'}
    styles=set('color background-color font-size font-weight font-style font-family text-align text-decoration padding padding-left padding-right margin margin-left margin-right border border-collapse width max-width height line-height'.split())
    def __init__(self,cids=None):
        super().__init__(convert_charrefs=True);self.out=[];self.text=[];self.skip=0;self.cids=cids or {}
    def handle_starttag(self,tag,attrs):
        if tag in self.blocked:
            if tag not in ('input','embed'):self.skip+=1
            return
        if self.skip or tag not in self.tags:return
        clean=[]
        for key,value in attrs:
            value=value or ''
            if key in ('colspan','rowspan','width','height') and re.fullmatch(r'[0-9]{1,4}%?',value):clean.append((key,value))
            if key in ('alt','title'):clean.append((key,value[:500]))
            if key=='style':
                parts=[]
                for part in value.split(';'):
                    name,sep,val=part.partition(':');name=name.strip().lower();val=val.strip()
                    if sep and name in self.styles and re.fullmatch(r'[a-zA-Z0-9 #.,%()\-]+',val) and not re.search(r'url|expression|import',val,re.I):parts.append(name+':'+val)
                if parts:clean.append(('style',';'.join(parts)))
            if tag=='img' and key=='src' and value.startswith('cid:') and value[4:] in self.cids:clean.append(('src',self.cids[value[4:]]))
        if tag=='img' and not any(k=='src' for k,v in clean):
            self.out.append('<span>[Image distante non chargée]</span>');return
        self.out.append('<'+tag+''.join(' '+k+'="'+escape(v,quote=True)+'"' for k,v in clean)+'>')
        if tag in ('p','div','br','li','tr','blockquote'):self.text.append('\n')
    def handle_endtag(self,tag):
        if tag in self.blocked:
            self.skip=max(0,self.skip-1);return
        if not self.skip and tag in self.tags and tag not in self.void:self.out.append('</'+tag+'>');self.text.append('\n' if tag in ('p','div','li','tr') else '')
    def handle_data(self,data):
        if not self.skip:self.out.append(escape(data));self.text.append(data)

def content(msg):
    plain=msg.get_body(preferencelist=('plain',));html=msg.get_body(preferencelist=('html',))
    cids={};total=0
    for part in msg.walk():
        cid=str(part.get('Content-ID','')).strip('<>');mime=part.get_content_type()
        if cid and mime in ('image/png','image/jpeg','image/gif','image/webp'):
            raw=part.get_payload(decode=True) or b'';total+=len(raw)
            if total<=5*1024*1024:cids[cid]='data:'+mime+';base64,'+base64.b64encode(raw).decode()
    parser=CleanHTML(cids)
    if html:parser.feed(str(html.get_content())[:500000]);parser.close()
    text=str(plain.get_content()) if plain else ''.join(parser.text)
    return {'body':text.strip()[:50000] or '[Message sans texte]', 'html':''.join(parser.out) if html else ''}

def message_data(msg,account,**ids):
    return {'account':account,**ids,'from':str(msg.get('From','')),'to':str(msg.get('To','')),
        'subject':str(msg.get('Subject','')),'date':str(msg.get('Date','')),
        'reply_to':str(msg.get('Reply-To') or msg.get('From','')),
        'message_id':str(msg.get('Message-ID','')),'references':str(msg.get('References','')),
        **content(msg)}
