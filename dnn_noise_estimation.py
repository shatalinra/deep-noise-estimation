import os, sys, logging, argparse, random
#os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import tensorflow as tf
import matplotlib.pyplot as plt
import data
import noise_estimator
from models import chuah_et_al, simple, efficient

# parse command line args
parser = argparse.ArgumentParser(description='Noise estimation DNN training script')
parser.add_argument('--log', help='Path to a log file.')
parser.add_argument('--validate', action='store_true', help='Validate model based on image separate from training or testing data.')
script_args = parser.parse_args()

# setup logging before anything else
log_format = '%(asctime)s: <%(levelname)s> %(message)s'
if script_args.log:
    try:
        error_stream = logging.StreamHandler()
        error_stream.setLevel(logging.INFO)
        log_file = logging.FileHandler(script_args.log)
        logging.basicConfig(format=log_format, level=logging.INFO, handlers=[error_stream, log_file])
    except OSError as err:
        print("Error while creating log {}: {}. Exiting...".format(err.filename, err.strerror))
        input("Press Enter to continue...")
        sys.exit(1)
else:
    logging.basicConfig(format=log_format, level=logging.INFO)

# now we can setup hooks for uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# giving message that log is indeed initialized
print("Log initialized")

#tf.debugging.set_log_device_placement(True)

# common procedure for training, evaluating and validating model
def try_model(name, patch_size, patch_stride, model_trainer, validate):
    logging.info("Trying " + name + " model")
    estimator = noise_estimator.NoiseEstimator(patch_size, patch_stride, model_trainer)
    try:
        # if everything will load fine we can go to testing the model
        estimator.load("trained_models/" + name)

        # generate testing data from a portion of MS COCO 2017 train images
        testing_patches, testing_labels = data.generate_dataset("../coco/2017/train/", 'dataset/test.txt', patch_size, patch_stride)
        logging.info("Testing data size %d", testing_labels.get_shape().as_list()[0])

        # now evaluate accuracy
        accuracy = estimator.evaluate(testing_patches, testing_labels)
        logging.info("Accuracy is %0.1f%%", 100 * accuracy)

    except IOError:
        # looks like we don't have trained model, so we have to train one from scratch
        # but first generate data on CPU in order to leave GPU RAM for model, training variables and batches
        with tf.device('/device:CPU:0'):
            training_patches, training_labels = data.generate_dataset("../coco/2017/train/", 'dataset/train.txt', patch_size, patch_stride)
            logging.info("Training data size %d", training_labels.get_shape().as_list()[0])

        estimator.train(training_patches, training_labels, "trained_models/" + name)

        # in order to not strain GPU memory we leave testing for separate run of the script

    if validate:
         # generate validation data
        noise_level = random.randint(0, 9)
        clean_image = data.load_image('../coco/2017/train/000000001955.jpg') # just taking image which should not be in train or test set
        validation_image = data.generate_image(clean_image, noise_level)
        logging.info("Actual noise level is %d", noise_level)

        # show original and noised image in order to check that noise generation is fine
        fig=plt.figure(figsize=(1, 2))
        fig.add_subplot(1, 2, 1)
        plt.imshow(clean_image)
        fig.add_subplot(1, 2, 2)
        plt.imshow(validation_image)
        plt.show()

        # run it though estimator
        classes, confidences = estimator(validation_image)
        for i in range(0, 9):
            logging.info("Estimated confidence in noise level %d: %.3f", classes[i], confidences[i])

# we start with trying models based on non-overlapping 32x32 patches which capture very little frame information
#try_model("chuah_et_al", 32, 32, chuah_et_al.train_model, script_args.validate)
try_model("simple", 32, 32, simple.train_model, script_args.validate)

# now we try pretrained models using overlapping 224x224 patches which should capture a lot of visual information
#try_model("efficent", 224, 4*224, efficient.train_model, script_args.validate)