"""
Example usage:

python load_tf_weights.py \
    --model_name efficientnet-b0 \
    --tf_checkpoint pretrained_tensorflow/efficientnet-b0/model.ckpt \
    --output_file pretrained_pytorch/efficientnet-b0.pth

Or for easier copying and pasting:

python load_tf_weights.py --model_name efficientnet-b0 --tf_checkpoint pretrained_tensorflow/efficientnet-b0/model.ckpt --output_file pretrained_pytorch/efficientnet-b0.pth
python load_tf_weights.py --model_name efficientnet-b1 --tf_checkpoint pretrained_tensorflow/efficientnet-b1/model.ckpt --output_file pretrained_pytorch/efficientnet-b1.pth
python load_tf_weights.py --model_name efficientnet-b2 --tf_checkpoint pretrained_tensorflow/efficientnet-b2/model.ckpt --output_file pretrained_pytorch/efficientnet-b2.pth
python load_tf_weights.py --model_name efficientnet-b3 --tf_checkpoint pretrained_tensorflow/efficientnet-b3/model.ckpt --output_file pretrained_pytorch/efficientnet-b3.pth
"""

import numpy as np
import tensorflow as tf
import torch

def load_param(checkpoint_file, conversion_table, model_name):
    """
    Load parameters according to conversion_table.

    Args:
        checkpoint_file (string): pretrained checkpoint model file in tensorflow
        conversion_table (dict): { pytorch tensor in a model : checkpoint variable name }
    """
    for pyt_param, tf_param_name in conversion_table.items():
        tf_param_name = str(model_name) + '/' +  tf_param_name
        tf_param = tf.train.load_variable(checkpoint_file, tf_param_name)
        if 'conv' in tf_param_name and 'kernel' in tf_param_name:
            tf_param = np.transpose(tf_param, (3, 2, 0, 1))
            if 'depthwise' in tf_param_name:
                tf_param = np.transpose(tf_param, (1, 0, 2, 3))
        elif tf_param_name.endswith('kernel'):  # for weight(kernel), we should do transpose
            tf_param = np.transpose(tf_param)
        assert pyt_param.size() == tf_param.shape, \
            'Dim Mismatch: %s vs %s ; %s' % (tuple(pyt_param.size()), tf_param.shape, tf_param_name)
        pyt_param.data = torch.from_numpy(tf_param)


def load_efficientnet(model, checkpoint_file, model_name):
    """
    Load PyTorch EfficientNet from TensorFlow checkpoint file
    """

    # This will store the enire conversion table
    conversion_table = {}
    merge = lambda dict1, dict2: {**dict1, **dict2}

    # All the weights not in the conv blocks
    conversion_table_for_weights_outside_blocks = {
        model._conv_stem.weight: 'stem/conv2d/kernel',  # [3, 3, 3, 32]),
        model._bn0.bias: 'stem/tpu_batch_normalization/beta',  # [32]),
        model._bn0.weight: 'stem/tpu_batch_normalization/gamma',  # [32]),
        model._bn0.running_mean: 'stem/tpu_batch_normalization/moving_mean',  # [32]),
        model._bn0.running_var: 'stem/tpu_batch_normalization/moving_variance',  # [32]),
        model._conv_head.weight: 'head/conv2d/kernel',  # [1, 1, 320, 1280]),
        model._bn1.bias: 'head/tpu_batch_normalization/beta',  # [1280]),
        model._bn1.weight: 'head/tpu_batch_normalization/gamma',  # [1280]),
        model._bn1.running_mean: 'head/tpu_batch_normalization/moving_mean',  # [32]),
        model._bn1.running_var: 'head/tpu_batch_normalization/moving_variance',  # [32]),
        model._fc.bias: 'head/dense/bias',  # [1000]),
        model._fc.weight: 'head/dense/kernel',  # [1280, 1000]),
    }
    conversion_table = merge(conversion_table, conversion_table_for_weights_outside_blocks)

    # The first conv block is special because it does not have _expand_conv
    conversion_table_for_first_block = {
        model._blocks[0]._project_conv.weight: 'blocks_0/conv2d/kernel',  # 1, 1, 32, 16]),
        model._blocks[0]._depthwise_conv.weight: 'blocks_0/depthwise_conv2d/depthwise_kernel',  # [3, 3, 32, 1]),
        model._blocks[0]._se_reduce.bias: 'blocks_0/se/conv2d/bias',  # , [8]),
        model._blocks[0]._se_reduce.weight: 'blocks_0/se/conv2d/kernel',  # , [1, 1, 32, 8]),
        model._blocks[0]._se_expand.bias: 'blocks_0/se/conv2d_1/bias',  # , [32]),
        model._blocks[0]._se_expand.weight: 'blocks_0/se/conv2d_1/kernel',  # , [1, 1, 8, 32]),
        model._blocks[0]._bn1.bias: 'blocks_0/tpu_batch_normalization/beta',  # [32]),
        model._blocks[0]._bn1.weight: 'blocks_0/tpu_batch_normalization/gamma',  # [32]),
        model._blocks[0]._bn1.running_mean: 'blocks_0/tpu_batch_normalization/moving_mean',
        model._blocks[0]._bn1.running_var: 'blocks_0/tpu_batch_normalization/moving_variance',
        model._blocks[0]._bn2.bias: 'blocks_0/tpu_batch_normalization_1/beta',  # [16]),
        model._blocks[0]._bn2.weight: 'blocks_0/tpu_batch_normalization_1/gamma',  # [16]),
        model._blocks[0]._bn2.running_mean: 'blocks_0/tpu_batch_normalization_1/moving_mean',
        model._blocks[0]._bn2.running_var: 'blocks_0/tpu_batch_normalization_1/moving_variance',
    }
    conversion_table = merge(conversion_table, conversion_table_for_first_block)

    # Conv blocks
    for i in range(len(model._blocks)):

        is_first_block = '_expand_conv.weight' not in [n for n, p in model._blocks[i].named_parameters()]

        if is_first_block:
            conversion_table_block = {
                model._blocks[i]._project_conv.weight: 'blocks_' + str(i) + '/conv2d/kernel',  # 1, 1, 32, 16]),
                model._blocks[i]._depthwise_conv.weight: 'blocks_' + str(i) + '/depthwise_conv2d/depthwise_kernel',
                # [3, 3, 32, 1]),
                model._blocks[i]._se_reduce.bias: 'blocks_' + str(i) + '/se/conv2d/bias',  # , [8]),
                model._blocks[i]._se_reduce.weight: 'blocks_' + str(i) + '/se/conv2d/kernel',  # , [1, 1, 32, 8]),
                model._blocks[i]._se_expand.bias: 'blocks_' + str(i) + '/se/conv2d_1/bias',  # , [32]),
                model._blocks[i]._se_expand.weight: 'blocks_' + str(i) + '/se/conv2d_1/kernel',  # , [1, 1, 8, 32]),
                model._blocks[i]._bn1.bias: 'blocks_' + str(i) + '/tpu_batch_normalization/beta',  # [32]),
                model._blocks[i]._bn1.weight: 'blocks_' + str(i) + '/tpu_batch_normalization/gamma',  # [32]),
                model._blocks[i]._bn1.running_mean: 'blocks_' + str(i) + '/tpu_batch_normalization/moving_mean',
                model._blocks[i]._bn1.running_var: 'blocks_' + str(i) + '/tpu_batch_normalization/moving_variance',
                model._blocks[i]._bn2.bias: 'blocks_' + str(i) + '/tpu_batch_normalization_1/beta',  # [16]),
                model._blocks[i]._bn2.weight: 'blocks_' + str(i) + '/tpu_batch_normalization_1/gamma',  # [16]),
                model._blocks[i]._bn2.running_mean: 'blocks_' + str(i) + '/tpu_batch_normalization_1/moving_mean',
                model._blocks[i]._bn2.running_var: 'blocks_' + str(i) + '/tpu_batch_normalization_1/moving_variance',
            }

        else:
            conversion_table_block = {
                model._blocks[i]._expand_conv.weight:       'blocks_' + str(i) + '/conv2d/kernel',
                model._blocks[i]._project_conv.weight:      'blocks_' + str(i) + '/conv2d_1/kernel',
                model._blocks[i]._depthwise_conv.weight:    'blocks_' + str(i) + '/depthwise_conv2d/depthwise_kernel',
                model._blocks[i]._se_reduce.bias:           'blocks_' + str(i) + '/se/conv2d/bias',
                model._blocks[i]._se_reduce.weight:         'blocks_' + str(i) + '/se/conv2d/kernel',
                model._blocks[i]._se_expand.bias:           'blocks_' + str(i) + '/se/conv2d_1/bias',
                model._blocks[i]._se_expand.weight:         'blocks_' + str(i) + '/se/conv2d_1/kernel',
                model._blocks[i]._bn0.bias:                 'blocks_' + str(i) + '/tpu_batch_normalization/beta',
                model._blocks[i]._bn0.weight:               'blocks_' + str(i) + '/tpu_batch_normalization/gamma',
                model._blocks[i]._bn0.running_mean:         'blocks_' + str(i) + '/tpu_batch_normalization/moving_mean',
                model._blocks[i]._bn0.running_var:          'blocks_' + str(i) + '/tpu_batch_normalization/moving_variance',
                model._blocks[i]._bn1.bias:                 'blocks_' + str(i) + '/tpu_batch_normalization_1/beta',
                model._blocks[i]._bn1.weight:               'blocks_' + str(i) + '/tpu_batch_normalization_1/gamma',
                model._blocks[i]._bn1.running_mean:         'blocks_' + str(i) + '/tpu_batch_normalization_1/moving_mean',
                model._blocks[i]._bn1.running_var:          'blocks_' + str(i) + '/tpu_batch_normalization_1/moving_variance',
                model._blocks[i]._bn2.bias:                 'blocks_' + str(i) + '/tpu_batch_normalization_2/beta',
                model._blocks[i]._bn2.weight:               'blocks_' + str(i) + '/tpu_batch_normalization_2/gamma',
                model._blocks[i]._bn2.running_mean:         'blocks_' + str(i) + '/tpu_batch_normalization_2/moving_mean',
                model._blocks[i]._bn2.running_var:          'blocks_' + str(i) + '/tpu_batch_normalization_2/moving_variance',
            }

        conversion_table = merge(conversion_table, conversion_table_block)

    # Load TensorFlow parameters into PyTorch model
    load_param(checkpoint_file, conversion_table, model_name)
    return conversion_table


if __name__ == '__main__':

    import sys
    import argparse
    sys.path.append('..')
    from utils import build_model

    parser = argparse.ArgumentParser(
        description='Convert TF model to PyTorch model and save for easier future loading')
    parser.add_argument('--model_name', type=str, default='efficientnet-b0',
                        help='efficientnet-b{N}, where N is an integer 0 <= N <= 7')
    parser.add_argument('--tf_checkpoint', type=str, default='pretrained_tensorflow/efficientnet-b0/model.ckpt',
                        help='checkpoint file path')
    parser.add_argument('--output_file', type=str, default='pretrained_pytorch/efficientnet-b0.pth',
                        help='output PyTorch model file name')
    args = parser.parse_args()

    # Build model
    model = build_model(args.model_name)

    # Load weights
    load_efficientnet(model, args.tf_checkpoint, model_name=args.model_name)
    print('Loaded TF checkpoint weights')

    # Save PyTorch file
    torch.save(model.state_dict(), args.output_file)
    print('Saved model to', args.output_file)
