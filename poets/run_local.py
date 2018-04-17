import tensorflow as tf
import poets as job_runner

import logging

logging.basicConfig(
    format='[%(asctime)s|%(name)s|%(levelname)s]: %(message)s',
    level='INFO')
log = logging.getLogger(__name__)

server = tf.train.Server.create_local_server()

context = {
    "args": {
        "--bottleneck_dir": "{{shared_filesystem}}/bottlenecks",
        "--how_many_training_steps": 500,
        "--model_dir": "{{shared_filesystem}}/models/",
        "--summaries_dir": "{{shared_filesystem}}/training_summaries/mobilenet_0.50_224",
        "--output_graph": "{{shared_filesystem}}/retrained_graph.pb",
        "--output_labels": "{{shared_filesystem}}/retrained_labels.txt",
        "--architecture": "mobilenet_0.50_224",
        "--image_dir": "hdfs:///tensorflow_input_data/flower_photos"
    }
}

job_runner.main(server, "tf_files", context)

log.info("Done")
