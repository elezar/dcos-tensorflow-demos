"""
A job to wrap the example at:
https://codelabs.developers.google.com/codelabs/tensorflow-for-poets/index.html?index=..%2F..%2Findex#0
"""
import argparse
import logging
import sys
import tensorflow as tf

import retrain


log = logging.getLogger(__name__)


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--image_dir',
        type=str,
        default='',
        help='Path to folders of labeled images.'
    )
    parser.add_argument(
        '--output_graph',
        type=str,
        default='/tmp/output_graph.pb',
        help='Where to save the trained graph.'
    )
    parser.add_argument(
        '--intermediate_output_graphs_dir',
        type=str,
        default='/tmp/intermediate_graph/',
        help='Where to save the intermediate graphs.'
    )
    parser.add_argument(
        '--intermediate_store_frequency',
        type=int,
        default=0,
        help="""\
            How many steps to store intermediate graph. If "0" then will not
            store.\
        """
    )
    parser.add_argument(
        '--output_labels',
        type=str,
        default='/tmp/output_labels.txt',
        help='Where to save the trained graph\'s labels.'
    )
    parser.add_argument(
        '--summaries_dir',
        type=str,
        default='/tmp/retrain_logs',
        help='Where to save summary logs for TensorBoard.'
    )
    parser.add_argument(
        '--how_many_training_steps',
        type=int,
        default=4000,
        help='How many training steps to run before ending.'
    )
    parser.add_argument(
        '--learning_rate',
        type=float,
        default=0.01,
        help='How large a learning rate to use when training.'
    )
    parser.add_argument(
        '--testing_percentage',
        type=int,
        default=10,
        help='What percentage of images to use as a test set.'
    )
    parser.add_argument(
        '--validation_percentage',
        type=int,
        default=10,
        help='What percentage of images to use as a validation set.'
    )
    parser.add_argument(
        '--eval_step_interval',
        type=int,
        default=10,
        help='How often to evaluate the training results.'
    )
    parser.add_argument(
        '--train_batch_size',
        type=int,
        default=100,
        help='How many images to train on at a time.'
    )
    parser.add_argument(
        '--test_batch_size',
        type=int,
        default=-1,
        help="""\
        How many images to test on. This test set is only used once, to evaluate
        the final accuracy of the model after training completes.
        A value of -1 causes the entire test set to be used, which leads to more
        stable results across runs.\
        """
    )
    parser.add_argument(
        '--validation_batch_size',
        type=int,
        default=100,
        help="""\
        How many images to use in an evaluation batch. This validation set is
        used much more often than the test set, and is an early indicator of how
        accurate the model is during training.
        A value of -1 causes the entire validation set to be used, which leads to
        more stable results across training iterations, but may be slower on large
        training sets.\
        """
    )
    parser.add_argument(
        '--print_misclassified_test_images',
        default=False,
        help="""\
        Whether to print out a list of all misclassified test images.\
        """,
        action='store_true'
    )
    parser.add_argument(
        '--model_dir',
        type=str,
        default='/tmp/imagenet',
        help="""\
        Path to classify_image_graph_def.pb,
        imagenet_synset_to_human_label_map.txt, and
        imagenet_2012_challenge_label_map_proto.pbtxt.\
        """
    )
    parser.add_argument(
        '--bottleneck_dir',
        type=str,
        default='/tmp/bottleneck',
        help='Path to cache bottleneck layer values as files.'
    )
    parser.add_argument(
        '--final_tensor_name',
        type=str,
        default='final_result',
        help="""\
        The name of the output classification layer in the retrained graph.\
        """
    )
    parser.add_argument(
        '--flip_left_right',
        default=False,
        help="""\
        Whether to randomly flip half of the training images horizontally.\
        """,
        action='store_true'
    )
    parser.add_argument(
        '--random_crop',
        type=int,
        default=0,
        help="""\
        A percentage determining how much of a margin to randomly crop off the
        training images.\
        """
    )
    parser.add_argument(
        '--random_scale',
        type=int,
        default=0,
        help="""\
        A percentage determining how much to randomly scale up the size of the
        training images by.\
        """
    )
    parser.add_argument(
        '--random_brightness',
        type=int,
        default=0,
        help="""\
        A percentage determining how much to randomly multiply the training image
        input pixels up or down by.\
        """
    )
    parser.add_argument(
        '--architecture',
        type=str,
        default='inception_v3',
        help="""\
        Which model architecture to use. 'inception_v3' is the most accurate, but
        also the slowest. For faster or smaller models, chose a MobileNet with the
        form 'mobilenet_<parameter size>_<input_size>[_quantized]'. For example,
        'mobilenet_1.0_224' will pick a model that is 17 MB in size and takes 224
        pixel input images, while 'mobilenet_0.25_128_quantized' will choose a much
        less accurate, but smaller and faster network that's 920 KB on disk and
        takes 128x128 images. See https://research.googleblog.com/2017/06/mobilenets-open-source-models-for.html
        for more information on Mobilenet.\
        """)

    return parser


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

    log.info("Using args=%s", args)

    parser = get_parser()
    FLAGS, unparsed = parser.parse_known_args(args)

    return FLAGS, unparsed


def main(server, log_dir, context):
    """
    This file is responsible for calling the retrain script and mapping entries in the `context` parameter
    to the FLAGS required by the retrain script.

    server: a tf.train.Server object (which knows about every other member of the cluster)
    log_dir: a string providing the recommended location for training logs, summaries, and checkpoints
    context: an optional dictionary of parameters (batch_size, learning_rate, etc.) specified at run-time
    """

    retrain.FLAGS, unparsed = get_args(context, log_dir)

    log.info("FLAGS=%s", retrain.FLAGS)
    log.info("unparsed=%s", unparsed)

    tf.app.run(main=retrain.main, argv=[sys.argv[0]] + unparsed)
