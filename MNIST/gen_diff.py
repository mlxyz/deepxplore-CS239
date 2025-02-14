'''
usage: python gen_diff.py -h
'''

from __future__ import print_function

import argparse
import tensorflow as tf
tf.compat.v1.disable_eager_execution()
from keras.datasets import mnist
from keras.layers import Input
from imageio import imwrite

from Model1 import Model1
from Model2 import Model2
from Model3 import Model3
from configs import bcolors
from utils import *

import pickle

GEN_INPUTS_DIR='../generated_inputs/MNIST/'

# read the parameter
# argument parsing
parser = argparse.ArgumentParser(description='Main function for difference-inducing input generation in MNIST dataset')
parser.add_argument('transformation', help="realistic transformation type", choices=['light', 'occl', 'blackout'])
parser.add_argument('weight_diff', help="weight hyperparm to control differential behavior", type=float)
parser.add_argument('weight_nc', help="weight hyperparm to control neuron coverage", type=float)
parser.add_argument('step', help="step size of gradient descent", type=float)
parser.add_argument('seeds', help="number of seeds of input", type=int)
parser.add_argument('grad_iterations', help="number of iterations of gradient descent", type=int)
parser.add_argument('threshold', help="threshold for determining neuron activated", type=float)
parser.add_argument('coverage', help='Coverage criteria targeted', choices=["nc", "snac"])
parser.add_argument('-t', '--target_model', help="target model that we want it predicts differently",
                    choices=[0, 1, 2], default=0, type=int)
parser.add_argument('-sp', '--start_point', help="occlusion upper left corner coordinate", default=(0, 0), type=tuple)
parser.add_argument('-occl_size', '--occlusion_size', help="occlusion size", default=(10, 10), type=tuple)


args = parser.parse_args()

random.seed(4172306)

# input image dimensions
img_rows, img_cols = 28, 28
# the data, shuffled and split between train and test sets
(_, _), (x_test, _) = mnist.load_data()

x_test = x_test.reshape(x_test.shape[0], img_rows, img_cols, 1)
input_shape = (img_rows, img_cols, 1)

x_test = x_test.astype('float32')
x_test /= 255

# define input tensor as a placeholder
input_tensor = Input(shape=input_shape)

# load multiple models sharing same input tensor
model1 = Model1(input_tensor=input_tensor)
model2 = Model2(input_tensor=input_tensor)
model3 = Model3(input_tensor=input_tensor)

# init coverage table
# model_layer_snac_dict = SNAC coverage (note: this impl uses SNAC to guide neuron selection as well)
# model_layer_snac_dict_only_test = measuring SNAC coverage from test data only (ignoring generated inputs from applied gradients)
# model_layer_nc_dict = NC coverage 
# model_layer_nc_ony_test = measuring 
m1_dict, m2_dict, m3_dict = {}, {}, {}

m1_dict["snac"], m2_dict["snac"], m3_dict["snac"] = init_coverage_tables(model1, model2, model3)
m1_dict["snac_test"], m2_dict["snac_test"], m3_dict["snac_test"] = init_coverage_tables(model1, model2, model3)
m1_dict["nc"], m2_dict["nc"], m3_dict["nc"] = init_coverage_tables(model1, model2, model3)
m1_dict["nc_test"], m2_dict["nc_test"], m3_dict["nc_test"] = init_coverage_tables(model1, model2, model3)

m1_hl = pickle.load(open("m1-10000-samples.p", "rb"), encoding='latin1')
m2_hl = pickle.load(open("m2-10000-samples.p", "rb"), encoding='latin1')
m3_hl = pickle.load(open("m3-10000-samples.p", "rb"), encoding='latin1')

def outputCoverage(m1, m2, m3, c):
    print(bcolors.OKGREEN + '%s percentage %d neurons %.3f, %d neurons %.3f, %d neurons %.3f'
              % (c, len(m1), neuron_covered(m1)[2], len(m2),
                 neuron_covered(m2)[2], len(m3),
                 neuron_covered(m3)[2]) + bcolors.ENDC)
    averaged_coverage = (neuron_covered(m1)[0] + neuron_covered(m2)[0] +
                       neuron_covered(m3)[0]) / float(
            neuron_covered(m1)[1] + neuron_covered(m2)[1] +
            neuron_covered(m3)[
                1])
    print(bcolors.OKGREEN + 'averaged %s %.3f' % (c, averaged_coverage) + bcolors.ENDC)


if args.coverage == "nc":
    print("\nRunning DeepXplore with coverage: Neuron Coverage")
elif args.coverage == "snac":
    print("\nRunning DeepXplore with coverage: SNAC")


# ==============================================================================================
# start gen inputs
random.shuffle(x_test)
x_test = x_test[:args.seeds]
iter = 0
differences = 0

for img in x_test:
    print("\nIteration " + str(iter+1))
    iter += 1
    gen_img = np.expand_dims(img, axis=0)
    orig_img = gen_img.copy()

    # first check if input already induces differences
    label1, label2, label3 = np.argmax(model1.predict(gen_img)[0]), np.argmax(model2.predict(gen_img)[0]), np.argmax(
        model3.predict(gen_img)[0])

    # measuring test-only coverage (ie don't include these only_test dictionaries when computing updated coverage
    # after applying gradients
    update_coverage(gen_img, model1, m1_dict, m1_hl, True, args.threshold)
    update_coverage(gen_img, model2, m2_dict, m2_hl, True, args.threshold)
    update_coverage(gen_img, model3, m3_dict, m3_hl, True, args.threshold)

    if not label1 == label2 == label3:
        print(bcolors.OKGREEN + 'input already causes different outputs: {}, {}, {}'.format(label1, label2,
                                                                                            label3) + bcolors.ENDC)

        update_coverage(gen_img, model1, m1_dict, m1_hl, args.threshold)
        update_coverage(gen_img, model2, m2_dict, m2_hl, args.threshold)
        update_coverage(gen_img, model3, m3_dict, m3_hl, args.threshold)

        outputCoverage(m1_dict["snac"], m2_dict["snac"], m3_dict["snac"], "SNAC")
        outputCoverage(m1_dict["nc"], m2_dict["nc"], m3_dict["nc"], "Neuron Coverage")

        gen_img_deprocessed = deprocess_image(gen_img)

        # save the result to disk
        imwrite(GEN_INPUTS_DIR + 'already_differ_' + str(label1) + '_' + str(
            label2) + '_' + str(label3) + '.png', gen_img_deprocessed)
        continue

    # if all label agrees
    orig_label = label1

    # construct joint loss function
    if args.target_model == 0:
        loss1 = -args.weight_diff * K.mean(model1.get_layer('before_softmax').output[..., orig_label])
        loss2 = K.mean(model2.get_layer('before_softmax').output[..., orig_label])
        loss3 = K.mean(model3.get_layer('before_softmax').output[..., orig_label])
    elif args.target_model == 1:
        loss1 = K.mean(model1.get_layer('before_softmax').output[..., orig_label])
        loss2 = -args.weight_diff * K.mean(model2.get_layer('before_softmax').output[..., orig_label])
        loss3 = K.mean(model3.get_layer('before_softmax').output[..., orig_label])
    elif args.target_model == 2:
        loss1 = K.mean(model1.get_layer('before_softmax').output[..., orig_label])
        loss2 = K.mean(model2.get_layer('before_softmax').output[..., orig_label])
        loss3 = -args.weight_diff * K.mean(model3.get_layer('before_softmax').output[..., orig_label])

    # we run gradient ascent for 20 steps
    for iters in range(args.grad_iterations):

        layer_name1, index1 = neuron_to_cover(m1_dict[args.coverage])
        layer_name2, index2 = neuron_to_cover(m2_dict[args.coverage])
        layer_name3, index3 = neuron_to_cover(m3_dict[args.coverage])
        loss1_neuron = model1.get_layer(layer_name1).output[0][np.unravel_index(index1,list(model1.get_layer(layer_name1).output.shape)[1:])]
        loss2_neuron = model2.get_layer(layer_name2).output[0][np.unravel_index(index2,list(model2.get_layer(layer_name2).output.shape)[1:])]
        loss3_neuron = model3.get_layer(layer_name3).output[0][np.unravel_index(index3,list(model3.get_layer(layer_name3).output.shape)[1:])]
        layer_output = (loss1 + loss2 + loss3) + args.weight_nc * (loss1_neuron + loss2_neuron + loss3_neuron)

        # for adversarial image generation
        final_loss = K.mean(layer_output)

        # we compute the gradient of the input picture wrt this loss
        grads = normalize(K.gradients(final_loss, input_tensor)[0])

        # this function returns the loss and grads given the input picture
        iterate = K.function([input_tensor], [loss1, loss2, loss3, loss1_neuron, loss2_neuron, loss3_neuron, grads])

        loss_value1, loss_value2, loss_value3, loss_neuron1, loss_neuron2, loss_neuron3, grads_value = iterate(
            [gen_img])
        if args.transformation == 'light':
            grads_value = constraint_light(grads_value)  # constraint the gradients value
        elif args.transformation == 'occl':
            grads_value = constraint_occl(grads_value, args.start_point,
                                          args.occlusion_size)  # constraint the gradients value
        elif args.transformation == 'blackout':
            grads_value = constraint_black(grads_value)  # constraint the gradients value

        gen_img += grads_value * args.step
        predictions1 = np.argmax(model1.predict(gen_img)[0])
        predictions2 = np.argmax(model2.predict(gen_img)[0])
        predictions3 = np.argmax(model3.predict(gen_img)[0])

        if not predictions1 == predictions2 == predictions3:
            update_coverage(gen_img, model1, m1_dict, m1_hl, args.threshold)
            update_coverage(gen_img, model2, m2_dict, m2_hl, args.threshold)
            update_coverage(gen_img, model3, m3_dict, m3_hl, args.threshold)

            print("Found new output which causes difference in models' predictions.")
            differences += 1
            outputCoverage(m1_dict["snac"], m2_dict["snac"], m3_dict["snac"], "SNAC")
            outputCoverage(m1_dict["nc"], m2_dict["nc"], m3_dict["nc"], "Neuron Coverage")

            gen_img_deprocessed = deprocess_image(gen_img)
            orig_img_deprocessed = deprocess_image(orig_img)

            # save the result to disk
            imwrite(GEN_INPUTS_DIR + args.transformation + '_' + str(predictions1) + '_' + str(
                predictions2) + '_' + str(predictions3) + '.png',
                   gen_img_deprocessed)
            imwrite(GEN_INPUTS_DIR + args.transformation + '_' + str(predictions1) + '_' + str(
                predictions2) + '_' + str(predictions3) + '_orig.png',
                   orig_img_deprocessed)
            break

print("Total differences found: %i" % differences)
print("Final coverage metric from test data with adversarial example generation: ")
outputCoverage(m1_dict["snac"], m2_dict["snac"], m3_dict["snac"], "SNAC")
outputCoverage(m1_dict["nc"], m2_dict["nc"], m3_dict["nc"], "Neuron Coverage")

print("Final coverage metric solely from test data: ")
outputCoverage(m1_dict["snac_test"], m2_dict["snac_test"], m3_dict["snac_test"], "SNAC")
outputCoverage(m1_dict["nc_test"], m2_dict["nc_test"], m3_dict["nc_test"], "Neuron Coverage")
