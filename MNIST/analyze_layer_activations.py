import pickle
import sys

# This file assumes that a dictionary of individual neurons' min+max values
# has already been computed and pickled, in the form:
# {(layer_name, index) -> (min, max)}
# The provided code effectively does a keyBy(layer_name) and aggregates
# min/max per layer.
# This file takes a single input argument, the pickled dictionary file.

f = sys.argv[1]
neuron_dict = pickle.load(open(f, "rb"))

layer_agg_dict = {}
for neuron_id, neuron_stats in neuron_dict.iteritems():
    (layer, _) = neuron_id
    neuron_min, neuron_max = neuron_stats
    if layer not in layer_agg_dict:
        layer_agg_dict[layer] = (neuron_min, neuron_max)
    else:
        layer_min, layer_max = layer_agg_dict[layer]
        layer_agg_dict[layer] = (min(neuron_min, layer_min), max(neuron_max, layer_max))

print("Printing layer-level minimum and maximum neuron activations for file %s" % (f,))
for layer, stats in layer_agg_dict.iteritems():
    print("Layer '%s' min/max: %s" % (layer, stats))

