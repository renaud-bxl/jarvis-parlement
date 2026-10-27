"""Modèles Word locaux : remplacement explicite d'une zone, conservation du reste."""
import copy
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4
from common import CONFIG, HOME, ROOT, atomic_json, read_json, settings

DIR = CONFIG / 'templates'
MARKER = '{{JARVIS_CONTENT}}'


def catalog():
    return read_json(DIR/'catalog.json', {'active':'', 'items':{}})


def seed():
    """Install anonymized starter layouts once, without selecting an institution for the user."""
    if (DIR/'catalog.json').exists(): return
    from docx import Document
    DIR.mkdir(parents=True,exist_ok=True,mode=0o700)
    cat={'active':'','items':{}}
    for source in (ROOT/'starter-templates').glob('*.docx'):
        ident=source.stem;target=DIR/(ident+'.docx');shutil.copy2(source,target);target.chmod(0o600)
        doc=Document(target);paragraphs=[{'index':i,'text':p.text[:250],'style':p.style.name} for i,p in enumerate(doc.paragraphs)]
        marker=next((i for i,p in enumerate(doc.paragraphs) if p.text.strip()==MARKER),None)
        cat['items'][ident]={'institution':'Parlement bruxellois','name':source.name,'ready':marker is not None,
            'start':marker,'end':marker,'paragraphs':paragraphs,'converted':False}
    atomic_json(DIR/'catalog.json',cat)


def import_template(data):
    from services import decode_file
    from docx import Document
    file=data.get('file',{}); suffix=Path(file.get('name','')).suffix.lower()
    if suffix not in ('.doc','.docx'): raise ValueError('Le modèle doit être un fichier .docx ou .doc.')
    institution=str(data.get('institution','')).strip()
    if not institution or len(institution)>100: raise ValueError('Indique le parlement ou l’institution.')
    raw=decode_file(file)
    DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    identifier=uuid4().hex; target=DIR/(identifier+'.docx')
    with tempfile.TemporaryDirectory() as folder:
        source=Path(folder)/('modele'+suffix); source.write_bytes(raw)
        if suffix=='.doc':
            result=subprocess.run(['textutil','-convert','docx','-output',str(target),str(source)],
                capture_output=True,timeout=90)
            if result.returncode or not target.exists(): raise ValueError('Conversion .doc impossible. Ouvre le modèle dans Word et enregistre-le en .docx.')
        else: target.write_bytes(raw)
    target.chmod(0o600)
    try: doc=Document(target)
    except Exception:
        target.unlink(missing_ok=True); raise ValueError('Document Word illisible.') from None
    if doc.element.xpath('//w:ins|//w:del|//w:commentRangeStart'):
        target.unlink(missing_ok=True)
        raise ValueError('Accepte les modifications suivies et retire les commentaires du modèle avant l’import.')
    paragraphs=[{'index':i,'text':p.text[:250],'style':p.style.name} for i,p in enumerate(doc.paragraphs)]
    markers=[i for i,p in enumerate(doc.paragraphs) if p.text.strip()==MARKER]
    entry={'institution':institution,'name':Path(file.get('name','modèle')).name,'ready':len(markers)==1,
        'start':markers[0] if len(markers)==1 else None,'end':markers[0] if len(markers)==1 else None,
        'paragraphs':paragraphs,'converted':suffix=='.doc'}
    cat=catalog();cat['items'][identifier]=entry
    if entry['ready']: cat['active']=identifier
    atomic_json(DIR/'catalog.json',cat)
    return {'id':identifier,**entry,'text':'Modèle importé. Vérifie la zone à remplacer et active-le.'}


def configure(data):
    from docx import Document
    cat=catalog(); ident=data.get('id')
    if ident not in cat['items']: raise ValueError('Modèle inconnu.')
    item=cat['items'][ident]; doc=Document(DIR/(ident+'.docx'))
    start,end=int(data.get('start',-1)),int(data.get('end',-1))
    if not 0<=start<=end<len(doc.paragraphs): raise ValueError('Sélectionne le premier et le dernier paragraphe à remplacer.')
    children=list(doc.element.body)
    a,b=(children.index(doc.paragraphs[i]._p) for i in (start,end))
    if any(node.xpath('.//w:sectPr') for node in children[a:b+1]):
        raise ValueError('Cette zone traverse un saut de section. Ajoute plutôt {{JARVIS_CONTENT}} dans un paragraphe dédié du modèle.')
    item.update(start=start,end=end,ready=True)
    if data.get('active',True): cat['active']=ident
    atomic_json(DIR/'catalog.json',cat)
    return {'text':'Modèle activé : '+item['institution']+'. Il sera appliqué aux prochains exports.'}


def activate(data):
    cat=catalog(); ident=data.get('id','')
    if ident and (ident not in cat['items'] or not cat['items'][ident]['ready']):
        raise ValueError('Configure la zone à remplacer avant d’activer ce modèle.')
    cat['active']=ident;atomic_json(DIR/'catalog.json',cat)
    return {'text':'Modèle actif modifié.'}


def export(text, title, output, identifier=None, fields=None):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph
    cat=catalog(); ident=cat['active'] if identifier is None else identifier
    if not ident: return False
    if ident not in cat['items'] or not cat['items'][ident]['ready']: raise ValueError('Modèle non configuré.')
    item=cat['items'][ident]; doc=Document(DIR/(ident+'.docx'))
    paragraphs=doc.paragraphs; first=paragraphs[item['start']]; last=paragraphs[item['end']]
    body=doc.element.body; children=list(body); a,b=children.index(first._p),children.index(last._p)
    ppr=copy.deepcopy(first._p.pPr)
    rpr=copy.deepcopy(first.runs[0]._r.rPr) if first.runs else None
    # A first paragraph style is used for body; named heading styles are kept in the template.
    anchor=OxmlElement('w:p'); body.insert(a,anchor)
    for child in children[a:b+1]: body.remove(child)
    content=text if '{{SUBJECT}}' in '\n'.join(p.text for p in paragraphs) else title+'\n\n'+text
    for line in content.splitlines():
        element=OxmlElement('w:p');anchor.addprevious(element)
        if ppr is not None: element.append(copy.deepcopy(ppr))
        p=Paragraph(element,doc._body)
        heading=re.match(r'^(#{1,3})\s+(.+)',line)
        if heading:
            style='Heading '+str(len(heading[1]))
            if style in doc.styles: p.style=doc.styles[style]
            line=heading[2]
        run=p.add_run(line)
        if rpr is not None and not heading: run._r.insert(0,copy.deepcopy(rpr))
    body.remove(anchor)
    cfg=settings(); fields=fields or {}
    values={'FULL_NAME':cfg.get('full_name') or '[Nom à préciser]',
        'ROLE':cfg.get('role') or '[Fonction à préciser]', 'INSTITUTION':cfg.get('institution') or item['institution'],
        'SUBJECT':fields.get('subject') or title,'RECIPIENT':fields.get('recipient') or '[Destinataire à préciser]',
        'SALUTATION':fields.get('salutation') or '[Formule d’appel à préciser]'}
    def replace(paras):
        for p in paras:
            value=p.text
            for key,entry in values.items(): value=value.replace('{{'+key+'}}',str(entry))
            if value!=p.text:
                old_rpr=copy.deepcopy(p.runs[0]._r.rPr) if p.runs else None
                p.clear();r=p.add_run(value)
                if old_rpr is not None:r._r.insert(0,old_rpr)
    replace(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:replace(cell.paragraphs)
    for section in doc.sections:
        for part in [section.header,section.first_page_header,section.even_page_header,
                section.footer,section.first_page_footer,section.even_page_footer]:replace(part.paragraphs)
    # No author-specific example text is sent to the model. Only the selected region is replaced.
    doc.save(output)
    return True


def pdf_from_docx(path):
    candidates=[Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
        HOME/'Applications/LibreOffice.app/Contents/MacOS/soffice']
    binary=next((str(p) for p in candidates if p.exists()),shutil.which('libreoffice') or shutil.which('soffice'))
    if not binary: raise ValueError('Export PDF du modèle : installe LibreOffice ou exporte le Word en PDF depuis ton traitement de texte.')
    with tempfile.TemporaryDirectory() as folder:
        result=subprocess.run([binary,'-env:UserInstallation='+Path(folder).as_uri(), '--headless',
            '--convert-to','pdf','--outdir',str(path.parent),str(path)],capture_output=True,timeout=120)
    if result.returncode or not path.with_suffix('.pdf').exists(): raise ValueError('Conversion PDF du modèle impossible ; le Word est conservé.')
    return path.with_suffix('.pdf')
