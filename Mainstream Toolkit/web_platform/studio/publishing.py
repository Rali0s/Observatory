"""Reuse original export and semantic modules; temporary files are isolated per request."""
import importlib.util
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from django.http import HttpResponse
from .engine import core


def module(name):
    if name in sys.modules: return sys.modules[name]
    sys.modules.setdefault('narrative_engine',core)
    if name=='publisher': module('analysis_engine')
    path=Path(__file__).resolve().parents[2]/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    loaded=importlib.util.module_from_spec(spec); sys.modules[name]=loaded; spec.loader.exec_module(loaded)
    return loaded


def export_edition(project,data):
    pub=module('publisher')
    rows=list(project.draft_chapters.all())
    chapters=[pub.Chapter(str(c.id),f'# {c.title}\n\n{c.markdown}') for c in rows]
    kind=data['format']
    if kind=='md':
        body='\n\n---\n\n'.join(c.markdown for c in chapters).encode(); mime='text/markdown'
    else:
        meta=pub.PublishMetadata(title=data['title'],author=data['author'],subtitle=data['subtitle'],copyright_year=str(date.today().year))
        with TemporaryDirectory(prefix='observatory-export-') as folder:
            art={}
            for c in rows:
                if c.art:
                    path=Path(folder)/(str(c.id)+{'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[c.art_type])
                    path.write_bytes(bytes(c.art));art[str(c.id)]=pub.ChapterArt(str(c.id),path,c.art_alt)
            args=[chapters,meta,data['title_page'],data['copyright_page']]
            if kind=='pdf':
                options=pub.PdfFormatOptions(trim_size=data['trim_size'],font_family=data['font_family'],font_size=data['font_size'],line_spacing=data['line_spacing'])
                path=pub.generate_pdf(*args,options,Path(folder),chapter_art=art);mime='application/pdf'
            else:
                path=pub.generate_epub(*args,Path(folder),chapter_art=art);mime='application/epub+zip'
            body=path.read_bytes()
    response=HttpResponse(body,content_type=mime)
    response['Content-Disposition']=f'attachment; filename="observatory-book.{kind}"'
    return response
