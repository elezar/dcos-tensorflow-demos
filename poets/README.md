# TensorFlow for Poets on DC/OS with Kerberized HDFS

This walkthrough will follow the steps described in the [TensorFlow for Poets](https://codelabs.developers.google.com/codelabs/tensorflow-for-poets/index.html?index=..%2F..%2Findex#0
) Google Codelab and adapt these to the DC/OS TensorFlow service.

The `0.2.0-1.5.0` version of the service is used, and the following points are highlighted:
* The use of Kerberized HDFS as a distributed backing store
* Handling off-the-shelf examples in the context of the DC/OS TensorFlow service

Note that this does not deal with model distribution directly, and assumes a single worker node for the time being.

## Prepare

This walkthrough is intended to be used with a Kerberized HDFS deployment such as DC/OS HDFS. This is not a requirement, and the HDFS-specifics can be swapped out with a different backing store. It is also possible to run this withough Kerberized HDFS -- meaning this is feasible for Open DC/OS clusters too.

The commands listed below assume that your DC/OS CLI is attached to a cluster running DC/OS version 1.10 or later. They also assume a permissive mode cluster, but there is no fundamental reason why they will not work on a strict mode cluster.

### Install KDC

If a KDC is not available, a simple KDC used for integration tests is available as part of the DC/OS commons repo. Clone this repo, and install the KDC with the principals required for HDFS:

```bash
git clone git@github.com:mesosphere/dcos-commons.git
cd dcos-commons
```

Create a virtual environment to install the KDCs python dependencies:
```bash
python3 -m venv kdc
source kdc/bin/activate
pip install -r test_requirements.txt
```

Assuming a file `demo/hdfs-principals.txt` exists in the current folder with the following contents:
```bash
cat demo/hdfs-principals.txt
hdfs/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/name-0-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/name-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/name-1-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/journal-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/journal-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/journal-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/data-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/data-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
hdfs/data-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/name-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/name-0-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/name-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/name-1-zkfc.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/journal-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/journal-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/journal-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/data-0-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/data-1-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/data-2-node.hdfs.autoip.dcos.thisdcos.directory@LOCAL
HTTP/api.hdfs.marathon.l4lb.thisdcos.directory@LOCAL
```

Run the following command to create a `__dcos_base64_hdfs_keytab` in the secret store conaining the relevant HDFS principals:
```bash
PYTHONPATH=testing tools/kdc/kdc.py --secret-name hdfs_keytab deploy demo/hdfs-principals.txt
```

Checking the list of secrets shows:
```bash
dcos security secrets list /
- __dcos_base64__hdfs_keytab
```

#### Create a TensorFlow client principal

At this stage we can also create a client principal and keytab for TensorFlow. First create the file `demo/tensorflow-principals.txt`:
```bash
cat demo/tensorflow-principals.txt
tensorflow@LOCAL
```
And create the DC/OS secret containing the keytab using the KDC utility:
```bash
PYTHONPATH=testing tools/kdc/kdc.py --secret-name tensorflow_keytab deploy demo/tensorflow-principals.txt
```
The secret has now been created as `__dcos_base64__tensorflow_keytab`:
```bash
dcos security secrets list /

- __dcos_base64__hdfs_keytab
- __dcos_base64__tensorflow_keytab
```

### Install HDFS

If kerberized HDFS is desired, create a `demo/hdfs.json` file with the following contents:
```bash
cat demo/hdfs.json
{
    "service": {
        "name": "hdfs",
        "security": {
            "kerberos": {
                "enabled": true,
                "debug": true,
                "kdc": {
                    "hostname": "kdc.marathon.autoip.dcos.thisdcos.directory",
                    "port": 2500
                },
                "realm": "LOCAL",
                "keytab_secret": "__dcos_base64__hdfs_keytab"
            }
        }
    },
    "hdfs": {
        "security_auth_to_local": "UlVMRTpbMjokMUAkMF0oXmhkZnNATE9DQUwkKXMvLiovaGRmcy8NClJVTEU6WzE6JDFAJDBdKF5oZGZzQExPQ0FMJClzLy4qL2hkZnMvDQpSVUxFOlsxOiQxQCQwXShedGVuc29yZmxvd0BMT0NBTCQpcy8uKi90ZW5zb3JmbG93Lw0KUlVMRTpbMTokMUAkMF0oXmFsaWNlQExPQ0FMJClzLy4qL2FsaWNlLw0KUlVMRTpbMTokMUAkMF0oXmJvYkBMT0NBTCQpcy8uKi9ib2IvDQo="
    }
}
```

Note that the contenst of the `hdfs.security_auth_to_local` option is the base64-encoded representation of:
```bash
cat demo/hdfs.json | jq -r .hdfs.security_auth_to_local | base64 --decode
RULE:[2:$1@$0](^hdfs@LOCAL$)s/.*/hdfs/
RULE:[1:$1@$0](^hdfs@LOCAL$)s/.*/hdfs/
RULE:[1:$1@$0](^tensorflow@LOCAL$)s/.*/tensorflow/
RULE:[1:$1@$0](^alice@LOCAL$)s/.*/alice/
RULE:[1:$1@$0](^bob@LOCAL$)s/.*/bob/
```
The last two rules are not required, but allow for testing of folder permissions. If desired these can be left out and the base64-encoded string adjusted accordingly.

Kerberized HDFS can now be installed as follows:
```bash
dcos package install --yes hdfs --options=demo/hdfs.json
```

### Prepare the filesystem

If TensorFlow is will not be run as the root (`hdfs`) user, it is required that the filesystem be set up accordingly so that the service has access to the specified folders.

These operations will be performed on one of the HDFS name nodes, but could also be performed on any client. Note that a principal that maps to an admin (`hdfs`) user is required. The principals of the HDFS cluster nodes are mapped to this user by the `RULE:[2:$1@$0](^hdfs@LOCAL$)s/.*/hdfs/` rule in the `hdfs.security_auth_to_local` configuration option.

Start an interactive shell on the name node:
```bash
dcos task exec -ti name-0-node bash
```

Set up the environment so that the Kerberized HDFS command line tools are available:
```bash
export JAVA_HOME=$(pwd)/jdk1.8.0_162
export KRB5_CONFIG=$(pwd)/hadoop-2.6.0-cdh5.11.0/etc/hadoop/krb5.conf
export HADOOP_OPTS="-Djava.security.krb5.conf=$KRB5_CONFIG"
```

Check the current contents of the HDFS root directory:
```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -ls /
```

#### Download the input data

As described in step 3 of the [TensorFlow for Poets codelab](https://codelabs.developers.google.com/codelabs/tensorflow-for-poets/index.html?index=..%2F..%2Findex#2), we must download the training images.

First create a local folder, as it is simpler to first download the images and then copy them to HDFS
```bash
mkdir tf_files
```

Now download the images:
```bash
curl http://download.tensorflow.org/example_images/flower_photos.tgz \
    | tar xz -C tf_files
```

Checking the contents of the folder
```bash
ls tf_files/flower_photos
```
shows:
```
daisy/
dandelion/
roses/
sunflowers/
tulips/
LICENSE.txt
```

#### Copy the input data to HDFS

In this example we will be using a different folder for the input data and the generated output data. Create a `tensorflow_input_data` folder on HDFS:

```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -mkdir /tensorflow_input_data
```

And copy the files downloaded in the previous step to this created folder:
```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -put tf_files/flower_photos /tensorflow_input_data/
```
*NOTE*: Depending on the cluster configuration, the copy may timeout, in which case it may be better to split the copy into 5 separate operations -- one for each of the subfolders of `flower_photos`.

Check that the files have been copied:
```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -ls /tensorflow_input_data/flower_photos
```

Note that the folders are owned by the `hdfs` superuser, but are world readable:
```
Found 6 items
-rw-r--r--   3 hdfs supergroup     418049 2018-04-17 10:17 /tensorflow_input_data/flower_photos/LICENSE.txt
drwxr-xr-x   - hdfs supergroup          0 2018-04-17 10:20 /tensorflow_input_data/flower_photos/daisy
drwxr-xr-x   - hdfs supergroup          0 2018-04-17 10:24 /tensorflow_input_data/flower_photos/dandelion
drwxr-xr-x   - hdfs supergroup          0 2018-04-17 10:29 /tensorflow_input_data/flower_photos/roses
drwxr-xr-x   - hdfs supergroup          0 2018-04-17 10:35 /tensorflow_input_data/flower_photos/sunflowers
drwxr-xr-x   - hdfs supergroup          0 2018-04-17 10:46 /tensorflow_input_data/flower_photos/tulips
```

#### Create the output folders

With the input data available, we need to create the folder to which TensorFlow will have write access. While still running an interactive terminal on the name node, we execute
```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -mkdir /tensorflow
```
to create the folder, and
```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -chown tensorflow:tensorflow /tensorflow
```
to change the ownership of the folder to the `tensorflow` local user. Note that the `tensorflow@LOCAL` principal created in a previous step will map to this user due to the `RULE:[1:$1@$0](^tensorflow@LOCAL$)s/.*/tensorflow/` authorization mapping rule.

Note that once this folder has been created and the permissions set, running
```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -ls /
```
shows that the root HDFS folder contains
```
Found 2 items
drwxr-xr-x   - tensorflow tensorflow          0 2018-04-17 11:59 /tensorflow
drwxr-xr-x   - hdfs       supergroup          0 2018-04-17 10:17 /tensorflow_input_data
```
Note the differences in ownership. It may be desireable to change the folder permissions of the `tensorflow` folder to non-world-readable using the `hdfs dfs -chmod` command.

## Implement the job file

Since the DC/OS TensorFlow service uses a [wrapper script](https://github.com/mesosphere/dcos-tensorflow/blob/master/frameworks/tensorflow/src/main/dist/tf_wrapper.py.mustache) to launch a TensorFlow job and expects a hook with the signature:
```python
def main(server, log_dir, context):
```
as an entrypoint, we need to do some work to adapt the code in the example from [Google Codelab](https://github.com/googlecodelabs/tensorflow-for-poets-2).

### Analysing the retraining script
Luckily, this is relatively straightforward as the training process in this case involves invoking a [retrain script](https://github.com/tensorflow/hub/blob/master/examples/image_retraining/retrain.py) with the right paramters.

When considering the
```python
if __name__ == "__main__":
```
section of [`retrain.py`](https://github.com/tensorflow/hub/blob/master/examples/image_retraining/retrain.py#L1159), we note that an `argparse` argument parser is set up, and this is used to set the global variable `FLAGS` and invoke `tensorflow.app.run()` as follows:
```python
FLAGS, unparsed = parser.parse_known_args()
tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)
```

### Creating a job launcher

Assuming we are happy with the default values defined in the argument parser, we could define our job as follows:
```python
import sys
import tensorflow as tf

import retrain


def get_parser():
    parser = argparse.ArgumentParser()
    # Add the default arguments as defined in the parser.py if __name__ == "__main__": section
    # ...

    return parser


def get_args(context, log_dir):
    parser = get_parser()

    FLAGS, unparsed = parser.parse_known_args([])

    return FLAGS, unparsed

def main(server, log_dir, context):
    retrain.FLAGS, unparsed = get_args(context, log_dir)
    tf.app.run(main=retrain.main, argv=[sys.argv[0]] + unparsed)
```

Where we have had to (unfortunately) duplicate the construction of the argument parser, but this is a relatively small change (we could always create an upstream PR that moves the creation of the parser into a function instead).

Note that when compared to the code in `retrain.py`, the `FLAGS` global variable and the `main` function are referenced relative to the `retrain` module -- asuming `retrain.py` is in the python path.

### Passing arguments to the job

In [Run the training](https://codelabs.developers.google.com/codelabs/tensorflow-for-poets/index.html?index=..%2F..%2Findex#3) step of the Google Codelab, the following arguments are needed for the `retrain.py` script:
```bash
python -m scripts.retrain \
  --bottleneck_dir=tf_files/bottlenecks \
  --how_many_training_steps=500 \
  --model_dir=tf_files/models/ \
  --summaries_dir=tf_files/training_summaries/"${ARCHITECTURE}" \
  --output_graph=tf_files/retrained_graph.pb \
  --output_labels=tf_files/retrained_labels.txt \
  --architecture="${ARCHITECTURE}" \
  --image_dir=tf_files/flower_photos
```

Since the DC/OS TensorFlow package supports a `service.job_context` parameter which is a string-encoded JSON object, we could add an `args` field to this context object and pass the required parameters through to our script in this manner:
```json
{
    "args": {
        "--bottleneck_dir": "{{shared_filesystem}}/bottlenecks",
        "--how_many_training_steps": 500,
        "--model_dir": "/mnt/mesos/sandbox/tf-volume/models/",
        "--summaries_dir": "{{shared_filesystem}}/training_summaries/mobilenet_0.50_224",
        "--output_graph": "{{shared_filesystem}}/retrained_graph.pb",
        "--output_labels": "{{shared_filesystem}}/retrained_labels.txt",
        "--architecture": "mobilenet_0.50_224",
        "--image_dir": "hdfs:///tensorflow_input_data/flower_photos"
    }
}
```
In order to process this item in the `service.job_context` configuration option (passed as a Python dictionary to the `main` hook), we adjust our `def get_args(context, log_dir)` function in the code snippet above as follows:
```python
def get_args(context, log_dir):
    """
    It is expected that the context have an `args` field which contains the arguments to be passed to the retrain
    script.

    Note that any parameter that contain `{{shared_filesystem}}` will have this template string replaced with
    the log_dir (`service.shared_filesystem` in config.json)
    """
    arg_dict = context.get("args", {})
    args = []

    for k, v in arg_dict.items():
        args.append(k)
        value = str(v).replace("{{shared_filesystem}}", log_dir)
        args.append(value)

    parser = get_parser()
    FLAGS, unparsed = parser.parse_known_args(args)

    return FLAGS, unparsed
```
Note the inclusion of a `{{shared_filesystem}}` mustache template parameter in some of the `args` keys, and there substitution with the `log_dir` which is set to the `service.shared_filesystem` configuraiton option if present.

*Note*:  the `--model_dir` value uses the `/mnt/mesos/sandbox/tf-volume` persistent volume and not an HDFS path. This is because the `retrain.maybe_download_and_extract` function does not support HDFS paths as it uses the Python `os` package directly.

## Distributing the job

Assuming we have a folder `poets` containing the files `retrain.py` downloaded from the Google Codelab GitHub repo and a file `poets.py` containing our job definition as discussed above, we could create a `poets.zip` file from this folder an distribute this for use as our `service.job_url` when launching DC/OS TensorFlow.

### Using GitHub

In order to make this more straightforward, I have created a GitHub repository containing the required files: https://github.com/elezar/dcos-tensorflow-demos.

The useful thing here is that GitHub automatically provides zip files that can be accessed by the Mesos fetcher for the job.

*Note*: This assumes the cluster running the example has access to the open internet and is not airgapped.

Using the repository above, the following `demos/poets.json` file can be created:
```json
{
    "service": {
        "name": "tensorflow",
        "security": {
            "kerberos": {
                "enabled": true,
                "kdc": {
                    "hostname": "kdc.marathon.autoip.dcos.thisdcos.directory",
                    "port": 2500
                },
                "primary": "tensorflow",
                "realm": "LOCAL",
                "keytab_secret": "__dcos_base64__tensorflow_keytab"
            }
        },
        "hdfs": {
            "config_uri": "http://api.hdfs.marathon.l4lb.thisdcos.directory/v1/endpoints"
        },
        "job_url": "https://github.com/elezar/dcos-tensorflow-demos/archive/master.zip",
        "job_path": "dcos-tensorflow-demos-master/poets",
        "job_name": "poets",
        "job_context": "{\r\n    \"args\": {\r\n        \"--bottleneck_dir\": \"{{shared_filesystem}}\/bottlenecks\",\r\n        \"--how_many_training_steps\": 500,\r\n        \"--model_dir\": \"\/mnt\/mesos\/sandbox\/tf-volume\/models\/\",\r\n        \"--summaries_dir\": \"{{shared_filesystem}}\/training_summaries\/mobilenet_0.50_224\",\r\n        \"--output_graph\": \"{{shared_filesystem}}\/retrained_graph.pb\",\r\n        \"--output_labels\": \"{{shared_filesystem}}\/retrained_labels.txt\",\r\n        \"--architecture\": \"mobilenet_0.50_224\",\r\n        \"--image_dir\": \"hdfs:\/\/default\/tensorflow_input_data\/flower_photos\"\r\n    }\r\n}",
        "shared_filesystem": "hdfs://default/tensorflow/test_run"
    },
    "parameter_server": {
        "count": 0
    },
    "worker": {
        "cpu": 4.0,
        "mem": 4096,
        "count": 1
    }
}
```

Where the following should be noted:
* The use of the HDFS deployment created earlier
* The Kerberos configuration matching for the KDC discussed earler
* The use of the `tensorflow@LOCAL` principal
* `service.job_url` pointing to the publically accessible master archive for the GitHub repo
* `service.job_path` indicating the path relative to the root of the extracted `master.zip` archive where the job definition is found
* `service.job_name` the name without extension of the Python file (`poets.py`) defining the job -- in turn invoking `retrain.main`
* `service.job_context` as a string-encoded JSON defining the `args` as discussed above
* `service.shared_filesystem` specifies a subfolder of the `tensorflow` folder on HDFS

## Deploying the job

Assuming that the `demo/poets.json` file has been created as required, the tensorflow job can be deployed as follows:
```bash
dcos package install --yes beta-tensorflow --options=demo/poets.json
```

Once the retraining process is complete the
```bash
dcos beta-tensorflow plan show deploy
```
comand shows the following output:
```
deploy (parallel strategy) (COMPLETE)
├─ gpuworker (parallel strategy) (COMPLETE)
├─ worker (parallel strategy) (COMPLETE)
│  └─ worker-0:[node] (COMPLETE)
└─ parameter-server (parallel strategy) (COMPLETE)
```

## Checking results

The contents of the `/tensorflow/test_run` folder on HDFS checked with the
```bash
hadoop-2.6.0-cdh5.11.0/bin/hdfs dfs -ls /tensorflow/test_run/
```
command on one of the name nodes shows:
```
Found 3 items
-rw-r--r--   3 tensorflow tensorflow    5488743 2018-04-17 12:48 /tensorflow/test_run/retrained_graph.pb
-rw-r--r--   3 tensorflow tensorflow         40 2018-04-17 12:48 /tensorflow/test_run/retrained_labels.txt
drwxr-xr-x   - tensorflow tensorflow          0 2018-04-17 12:31 /tensorflow/test_run/training_summaries
```
Where `/tensorflow/test_run/retrained_graph.pb` is a new TensorFlow model file which can be used for inferrence and labelling tasks and the `/tensorflow/test_run/training_summaries` contains the summaries showing the output of the retraining process.

The log output of the worker task
```bash
dcos task log worker-0-node__19e6259b-43e0-4b3a-a817-da1ab7272718 stderr --completed
```
Shows the accuracy of the model
```
INFO:tensorflow:2018-04-17 12:48:42.927011: Step 499: Train accuracy = 98.0%
[2018-04-17 12:48:42,927|tensorflow|INFO]: 2018-04-17 12:48:42.927011: Step 499: Train accuracy = 98.0%
INFO:tensorflow:2018-04-17 12:48:42.927220: Step 499: Cross entropy = 0.077798
[2018-04-17 12:48:42,927|tensorflow|INFO]: 2018-04-17 12:48:42.927220: Step 499: Cross entropy = 0.077798
INFO:tensorflow:2018-04-17 12:48:42.957614: Step 499: Validation accuracy = 85.0% (N=100)
[2018-04-17 12:48:42,957|tensorflow|INFO]: 2018-04-17 12:48:42.957614: Step 499: Validation accuracy = 85.0% (N=100)
INFO:tensorflow:Final test accuracy = 86.7% (N=383)
[2018-04-17 12:48:43,140|tensorflow|INFO]: Final test accuracy = 86.7% (N=383)
INFO:tensorflow:Froze 2 variables.
[2018-04-17 12:48:43,173|tensorflow|INFO]: Froze 2 variables.
```
