#!/bin/bash
# for each iteration, prints DX-NC and True-NC (name??). Note that True-NC calculates individual neuron coverage based on the unscaled activation output.
mkdir -p official_report_results

# MNIST

(cd MNIST && python gen_diff.py light 1 0.1 10 500 20 0) | tee official_report_results/mnist_500_original_light.log > /dev/null &
(cd MNIST && python gen_diff.py occl 1 0.1 10 500 20 0) | tee official_report_results/mnist_500_original_occl.log > /dev/null &
(cd MNIST && python gen_diff.py blackout 1 0.1 10 500 20 0) | tee official_report_results/mnist_500_original_blackout.log > /dev/null &

# # Driving
(cd Driving && python gen_diff.py light 1 0.1 10 500 20 0) | tee official_report_results/driving_500_original_light.log > /dev/null &
(cd Driving && python gen_diff.py occl 1 0.1 10 500 20 0) | tee official_report_results/driving_500_original_occl.log > /dev/null &
(cd Driving && python gen_diff.py blackout 1 0.1 10 500 20 0) | tee official_report_results/driving_500_original_blackout.log > /dev/null &

# # PDF
(cd PDF && python gen_diff.py 2 0.1 0.1 500 20 0) | tee official_report_results/pdf_500_original.log > /dev/null &
