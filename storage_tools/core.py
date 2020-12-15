# AUTOGENERATED! DO NOT EDIT! File to edit: 00_core.ipynb (unless otherwise specified).

__all__ = ['read_config', 'parse_dataset_archive_name', 'parse_dataset_archive_version', 'next_version', 'sha256',
           'make_or_update_manifest', 'check_archive', 'make_dataset_archive_folder', 'StorageClientABC',
           'LocalStorageClient', 'AzureStorageClient', 'AwsStorageClient', 'new_storage_client']

# Cell
from abc import ABC,abstractmethod
from configparser import ConfigParser
from pathlib import Path
import azure.storage.blob,azure.core.exceptions
import boto3
import shutil,re,json,hashlib,datetime
from typing import List,Tuple,Optional,Union

# Cell
def read_config(section_name:str=None,config_name:str='secrets/settings.ini'):
    config_path=Path(config_name)
    config=ConfigParser()
    config.read(config_path)
    if section_name is None:
        return config
    if section_name not in config:
        raise Exception(f'Error: [{section_name}] section not found in {config_path}')
    return dict(config.items(section_name))

# Cell
def parse_dataset_archive_name(name:str) -> Optional[Tuple[str,...]]:
    "Returns (name,version) if `name` is a dataset archive name, `None` otherwise"
    match = re.match('^([\./\s\w-]+)\.(\d+\.\d+\.\d+)\.zip$',name)
    return None if match is None else match.group(1,2)

# Cell
def parse_dataset_archive_version(version:str) -> List[int]:
    "Returns (major,minor,patch) if `version` is a valid dataset archive version"
    match = re.match('^(\d+)\.(\d+)\.(\d+)$',version)
    if match is None: raise ValueError(f'Invalid version: {version}')
    return [int(s) for s in match.group(1,2,3)]

# Cell
def next_version(versions:List[str]=None,increment:str='patch'):
    "Return the version that should follow the last version in `versions`"
    v=[0,0,0] if versions is None else parse_dataset_archive_version(versions[-1])
    if increment=='patch': v[2]+=1
    elif increment=='minor': v[1]+=1;v[2]=0
    elif increment=='major': v[0]+=1;v[1]=0;v[2]=0
    else: raise ValueError(f'Unknown increment: {increment}')
    return f'{v[0]}.{v[1]}.{v[2]}'

# Cell
def sha256(file:Union[Path,str]) -> str:
    "Return the secure hash (as a hex digest) of the specified file"
    m = hashlib.sha256()
    with open(file,'rb') as f: m.update(f.read())
    return m.hexdigest()

# Cell
def _get_manifest(archive_folder):
    "Returns (archive folder path, manifest file path, manifest as dict)"
    p=Path(archive_folder)
    mf=p/'manifest.json'
    if mf.is_file():
        with open(mf) as f: m=json.load(f)
    else:
        m={}
    return p,mf,m

def make_or_update_manifest(archive_folder:Union[Path,str]):
    "Create or update a manifest in `archive_folder`"
    p,mf,m=_get_manifest(archive_folder)
    m['datetime']=datetime.datetime.utcnow().isoformat()
    m['files']=[]
    len_p=len(str(p).replace('\\','/'))
    for f in [f for f in p.rglob('*') if f.is_file()]:
        m['files'].append(dict(
            file=str(f).replace('\\','/')[len_p+1:],
            sha256=sha256(f)))
    with open(mf,'w') as f: json.dump(m,f,indent=2,sort_keys=True)

def check_archive(archive_folder:Union[Path,str]):
    "Check that all files listed in manifest.json have the correct secure hash"
    p,mf,m=_get_manifest(archive_folder)
    for file in m['files']:
        expected,actual=file['sha256'],sha256(p/file['file'])
        if actual!=expected:
            raise ValueError(f"sha mismatch for {file['file']}. Expected {expected} but found {actual}")

# Cell
def make_dataset_archive_folder(
        path:str, name:str, versions:List[str]=None, version:str='patch') -> str:
    "Create a new dataset archive folder in `path`"
    src=Path(path)/name
    if not src.exists(): raise FileNotFoundError(f'{src} not found')

    if version in ['major','minor','patch']:
        version=next_version(versions,version)
    else:
        parse_dataset_archive_version(version)

    archive_folder=Path(path)/'.'.join([name,version])
    if archive_folder.exists():
        raise FileExistsError(f'Archive folder {archive_folder} exists')
    if src.is_file():
        archive_folder.mkdir(parents=True)
        shutil.copy(src,archive_folder)
    else:
        shutil.copytree(src,archive_folder)
    make_or_update_manifest(archive_folder)
    return f'{path}/{name}.{version}'

# Cell
class StorageClientABC(ABC):
    """Defines functionality common to all storage clients"""

    def __init__(self, config:dict):
        "Create a new storage client using the specified `config`"
        self.config=config

    def ls(self, what:str='storage_area',name_starts_with:str=None) -> List[str]:
        "Return a list containing the names of files in either `storage_area` or `local_path`"
        p=Path(self.config[what])
        p.mkdir(parents=True,exist_ok=True)
        len_p=len(str(p).replace('\\','/'))
        result=[str(f).replace('\\','/')[len_p+1:] for f in p.rglob('*') if f.is_file()]
        if name_starts_with is not None:
            result=[r for r in result if r.startswith(name_starts_with)]
        return sorted(result)

    @abstractmethod
    def download(self, filename:str) -> Path:
        "Copy `filename` from `storage_area` to `local_path`"

    @abstractmethod
    def upload(self, filename:str, overwrite=False) -> Union[Path,str]:
        "Copy `filename` from `local_path` to `storage_area`"

    def _sort_by_dataset_archive_version(self,version):
        try: return tuple(parse_dataset_archive_version(version))
        except: return (-1,-1,-1)

    def ls_versions(self, name:str, what:str='storage_area') -> Union[List[str],None]:
        "Return a list containing all versions of the specified archive `name`"
        files=[parse_dataset_archive_name(f) for f in self.ls(what)]
        result=[f[1] for f in files if f is not None and f[0]==name]
        if not result: return None
        return sorted(result, key=self._sort_by_dataset_archive_version)

    def upload_dataset(self, name:str, version:str='patch') -> Union[Path,str]:
        "Create a new dataset archive and upload it to `storage_area`"
        archive_folder=make_dataset_archive_folder(
                self.config['local_path'],name,self.ls_versions(name),version)
        archive=shutil.make_archive(archive_folder,'zip',archive_folder)
        return self.upload(f"{archive_folder[len(self.config['local_path'])+1:]}.zip")

    def download_dataset(self, name:str, version:str='latest', overwrite:bool=False) -> Path:
        "Download a dataset archive from `storage_area` and extract it to `local_path`"
        if version=='latest':
            versions=self.ls_versions(name)
            if versions is None:
                raise ValueError('latest version requested but no versions exist in storage area')
            version=versions[-1]
        dst=Path(self.config['local_path'])/f'{name}.{version}'
        if dst.exists():
            if not overwrite: return dst
            else: shutil.rmtree(dst)
        archive=self.download(f'{name}.{version}.zip')
        shutil.unpack_archive(str(archive),dst)
        check_archive(dst)
        return dst

# Cell
class LocalStorageClient(StorageClientABC):
    """Storage client that uses the local filesystem for both `storage_area` and `local_path`"""

    def _cp(self,from_key,to_key,filename,overwrite=False):
        src=Path(self.config[from_key])/filename
        dst=Path(self.config[to_key])/filename
        if dst.exists() and not overwrite:
            raise FileExistsError(f'{dst} exists and overwrite=False')
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy(src,dst)
        return dst

    def download(self,filename,overwrite=False):
        try: self._cp('storage_area','local_path',filename,overwrite)
        except FileExistsError: pass
        return Path(self.config['local_path'])/filename

    def upload(self,filename,overwrite=False):
        return self._cp('local_path','storage_area',filename,overwrite)

# Cell
class AzureStorageClient(StorageClientABC):
    """Storage client that uses Azure for `storage_area` and the local filesystem `local_path`"""

    @property
    def client(self):
        if not hasattr(self,'_client'):
            service_client=azure.storage.blob.BlobServiceClient.from_connection_string(
                self.config['conn_str'],self.config['credential'])
            self._client=service_client.get_container_client(self.config['container'])
        return self._client

    def ls(self,what='storage_area',name_starts_with=None):
        if what=='local_path': return super().ls(what,name_starts_with)
        result=[b.name for b in self.client.list_blobs(name_starts_with)]
        return sorted(result)

    def download(self,filename,overwrite=False):
        p=Path(self.config['local_path'])/filename
        if p.exists() and not overwrite: return p
        p.parent.mkdir(parents=True,exist_ok=True)
        with open(p, 'wb') as f:
            f.write(self.client.download_blob(filename).readall())
        return p

    def upload(self,filename,overwrite=False):
        p=Path(self.config['local_path'])/filename
        try:
            with open(p, 'rb') as f:
                self.client.upload_blob(filename,f,overwrite=overwrite)
            return f"{self.config['storage_type']}:{self.config['container']}:{filename}"
        except azure.core.exceptions.ResourceExistsError as e:
            raise FileExistsError(f'{e}\noverwrite=False')

# Cell
class AwsStorageClient(StorageClientABC):
    """Storage client that uses AWS for `storage_area` and the local filesystem `local_path`"""

    @property
    def client(self):
        if not hasattr(self,'_client'):
            self._client=boto3.client(service_name=self.config['service_name'],
                                      aws_access_key_id=self.config['aws_access_key_id'],
                                      aws_secret_access_key=self.config['aws_secret_access_key'])
        return self._client

    def ls(self,what='storage_area',name_starts_with=None):
        if what=='local_path': return super().ls(what,name_starts_with)
        args=dict(Bucket=self.config['bucket'])
        if name_starts_with is not None: args['Prefix']=name_starts_with
        objects=self.client.list_objects_v2(**args)
        if objects['KeyCount']==0: return []
        result=[o['Key'] for o in objects['Contents'] if o['Size']>0]
        return sorted(result)

    def download(self,filename):
        p=Path(self.config['local_path'])/filename
        if p.exists() and not overwrite: return p
        p.parent.mkdir(parents=True,exist_ok=True)
        self.client.download_file(
                Filename='/'.join([self.config['local_path'],filename]),
                Bucket=self.config['bucket'],
                Key=filename)
        return p

    def upload(self,filename,overwrite=False):
        result=f"{self.config['storage_type']}:{self.config['bucket']}:{filename}"
        if overwrite==False and filename in [self.ls(name_starts_with=filename)]:
            raise FileExistsError(f'{result} exists and overwrite=False')
        self.client.upload_file(
                Filename='/'.join([self.config['local_path'],filename]),
                Bucket=self.config['bucket'],
                Key=filename)
        return result

# Cell
def new_storage_client(storage_name:str,config_name:str='secrets/settings.ini'):
    "Returns a storage client based on the configured `storage_type`"
    config=read_config(storage_name,config_name=config_name)
    storage_type=config['storage_type']
    if storage_type=='local': return LocalStorageClient(config)
    elif storage_type=='azure': return AzureStorageClient(config)
    elif storage_type=='aws': return AwsStorageClient(config)
    else: raise ValueError(f'Unknown storage_type: {storage_type}')