# Storage tools
> The goal of this project is to make it easy to work with local or cloud storage as part of a data science workflow.


## Key Features

### You can access a dataset with a single command ...

e.g. `download_dataset azure_demo mnist/hand_drawn_digits`

### ... or a few lines of python

Just import the storage tools core module, create a client and download your dataset.

### You don't put secret keys in your code

Secret keys live in their own files and storage tools knows how to find them.

### Datasets are version controlled

Storage tools makes it easy to 
- manage multiple versions of a dataset and
- know which version of the dataset you are working with locally.

## Install

`pip install storage_tools`

## Storage tools conventions

We recommend that you ...

### Use forward slashes on all platforms

Use forward slashes when specifying files, paths and dataset names.

### Avoid whitespace and special characters in file and path names

### Use folders for secrets and data

<pre>
project_root
  &angrt; data
  &angrt; secrets
    &angrt; settings.ini
</pre>

Add the following to `.gitignore`
```
secrets/
data/
```

Add the following to `settings.ini`
```
[DEFAULT]
local_path=data
```

Running storage_client from your project root will read `project_root/secrets/settings.ini` and save all local data to `project_root/data`

## How to use azure storage

If we follow the above conventions and have a project folder containing

<pre>
project_root
  &angrt; data
    &angrt; mnist
      &angrt; hand_drawn_digits
        &angrt; digit0.png
        &angrt; digit1.png
        &angrt; ...
  &angrt; secrets
    &angrt; settings.ini
&angrt; main.py
</pre>

where `settings.ini` contains

```
[DEFAULT]
local_path=data

[azure_demo]
storage_client=storage_tools.core.AzureStorageClient
conn_str=<A connection string to an Azure Storage account without credential>
credential=<The credentials with which to authenticate>
container=<The name of a storage container>
```

We can use `main.py` to

### Create a new storage_client

```
storage_client=new_storage_client('azure_demo')
```

### List files in the azure container (remote)

```
storage_client.ls()
```

### List files in data (local)

```
storage_client.ls('local_path')
```

### Create a new version of a dataset

```
storage_client.upload_dataset('mnist/hand_drawn_digits','major')
```

Note: If you run `storage_client.ls()` again, you'll see the new file in the azure container.

### Download the latest version of a dataset

Feel free to delete your local copy of this dataset (from data) to download from azure storage.

```
storage_client.download_dataset('mnist/hand_drawn_digits')
```

Note: If you run `storage_client.ls('local_path')` again, you'll see the dataset in data.

See [BlobServiceClient docs](https://docs.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobserviceclient?view=azure-python) for more details on the settings used in `settings.ini`
- `from_connection_string` (`conn_str` and `credential`)
- `get_container_client` (`container`)

## How to use AWS storage

It's the same as Azure except `settings.ini` contains

```
[DEFAULT]
local_path=data

[aws_demo]
storage_client=storage_tools.core.AwsStorageClient
service_name=s3
aws_access_key_id=<An AWS access key ID>
aws_secret_access_key=<An AWS access key>
bucket=<The name of an AWS bucket that the access key is allowed to read from and write to>
```

# Developers

```
git config --global core.autocrlf input
```

```
!pip install fastcore
!pip install boto3
!pip install azure-storage-blob
```

## Type checking with mypy

```
!pip install mypy
```

Then from the storage_tools project folder
```
nbdev_build_lib
mypy storage_tools/core.py
```

For now, I'm ignoring the "Skipping analyzing 'azure': found module but no type hints or library stubs" error
