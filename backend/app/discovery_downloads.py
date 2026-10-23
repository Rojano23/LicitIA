"""Bounded public download, only after explicit handoff selection. Never analyzes files."""
from dataclasses import dataclass
from datetime import datetime,timezone
from tempfile import SpooledTemporaryFile
from pathlib import PurePosixPath
import hashlib,time

MAX_BYTES=25*1024*1024
MAX_SECONDS=60
class DownloadError(ValueError):pass
@dataclass
class Downloaded:
    filename:str
    content_type:str
    file:object
    sha256:str
    downloaded_at:datetime
    def close(self):self.file.close()

def filename(value):
    if not isinstance(value,str) or not value.strip() or len(value)>255 or value!=value.strip() or '/' in value or '\\' in value or value in {'.','..'} or any(ord(c)<32 or ord(c)==127 for c in value):
        raise DownloadError('UNSAFE_SOURCE_FILENAME')
    if PurePosixPath(value).name!=value or any(c in value for c in ':*?"<>|'):raise DownloadError('UNSAFE_SOURCE_FILENAME')
    if value.endswith('.') or len(value.encode('utf-8'))>255 or value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:raise DownloadError('UNSAFE_SOURCE_FILENAME')
    return value

def download(client,doc,validator):
    url=validator(doc.public_url);name=filename(doc.name);start=time.monotonic();stream=SpooledTemporaryFile(max_size=1024*1024,mode='w+b')
    try:
        with client.stream('GET',url,headers={'Accept':'*/*'},timeout=30) as response:
            if response.status_code!=200:raise DownloadError('SOURCE_DOWNLOAD_HTTP_'+str(response.status_code))
            mime=response.headers.get('content-type','').split(';')[0].lower().strip()
            allowed={'application/pdf','application/octet-stream','application/zip','application/x-zip-compressed','application/x-rar-compressed','application/vnd.rar','application/x-7z-compressed',
                'application/msword','application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','text/plain','text/csv','image/png','image/jpeg','image/tiff'}
            if mime not in allowed:raise DownloadError('UNSUPPORTED_SOURCE_MIME')
            digest=hashlib.sha256();size=0;prefix=b''
            for chunk in response.iter_bytes():
                if time.monotonic()-start>MAX_SECONDS:raise DownloadError('SOURCE_DOWNLOAD_CEILING')
                size+=len(chunk)
                if size>MAX_BYTES:raise DownloadError('SOURCE_DOWNLOAD_SIZE_LIMIT')
                prefix=(prefix+chunk)[:1024];digest.update(chunk);stream.write(chunk)
            if not size:raise DownloadError('EMPTY_SOURCE_FILE')
            leading=prefix.lstrip().lower()
            if leading.startswith((b'<!doctype html',b'<html',b'<script')):raise DownloadError('HTML_IS_NOT_A_DOCUMENT')
            binary=prefix.startswith((b'%PDF-',b'PK\x03\x04',b'PK\x05\x06',b'Rar!\x1a\x07',b'7z\xbc\xaf\x27\x1c',b'\xd0\xcf\x11\xe0',b'\x89PNG',b'\xff\xd8\xff',b'II*\x00',b'MM\x00*'))
            if mime=='application/pdf' and not prefix.startswith(b'%PDF-'):raise DownloadError('PDF_SIGNATURE_MISMATCH')
            if mime!='text/plain' and mime!='text/csv' and not binary:raise DownloadError('SOURCE_SIGNATURE_MISMATCH')
            expected={
                'application/zip':(b'PK\x03\x04',b'PK\x05\x06'),'application/x-zip-compressed':(b'PK\x03\x04',b'PK\x05\x06'),
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document':(b'PK\x03\x04',),
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':(b'PK\x03\x04',),
                'application/msword':(b'\xd0\xcf\x11\xe0',),'application/vnd.ms-excel':(b'\xd0\xcf\x11\xe0',),
                'application/x-rar-compressed':(b'Rar!\x1a\x07',),'application/vnd.rar':(b'Rar!\x1a\x07',),
                'application/x-7z-compressed':(b'7z\xbc\xaf\x27\x1c',),'image/png':(b'\x89PNG',),
                'image/jpeg':(b'\xff\xd8\xff',),'image/tiff':(b'II*\x00',b'MM\x00*')}
            if mime in expected and not prefix.startswith(expected[mime]):raise DownloadError('SOURCE_MIME_SIGNATURE_MISMATCH')
            if mime in {'text/plain','text/csv'}:
                if binary:raise DownloadError('INVALID_TEXT_DOCUMENT')
                if b'\x00' in prefix:raise DownloadError('INVALID_TEXT_DOCUMENT')
                import codecs
                codecs.getincrementaldecoder('utf-8')().decode(prefix,final=size<=1024)
            stream.seek(0);return Downloaded(name,mime,stream,digest.hexdigest(),datetime.now(timezone.utc))
    except Exception:
        stream.close();raise
