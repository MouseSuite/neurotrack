.. Neuron Tracking documentation master file, created by
   sphinx-quickstart on Thu Feb  6 11:21:30 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Neurotrack's documentation!
===========================================

Features
--------

- Load and simulate microscopy images from existing morphology saved in SWC file format.
- Simulate neuron tree morphology de novo.
- Perform neurite tracking to reconstruct neuron morphology.

Overview
--------

This package provides tools for performing neuron tracking using simulated fluorescence microscopy data. It includes functions for
generating simulated data, collecting data and training a branch point classification model, and performing tracking to
reconstruct neuron morphology.

Neuron tracking is performed sequentially, starting from a seed point and stepping along the neuron until the end is reached. It uses two independent neural network models for the tracking process: 
1. Actor -- A deep convolutional neural network which takes 3D RGB image patches as input and outputs the mean and standard deviation for a multivariate Gaussian from which the next step direction is sampled.  
2. Branch classifier -- A residual neural network (ResNet) which takes 3D grayscale image patches as input and outputs a number representing the probability that the patch is centered on a neuron branch.

The actor network is trained using the soft actor-critic reinforcement learning algorithm which jointly optimizes a value function and a policy function. The value function aims to estimate the value (sum of future discounted rewards) of state-action pairs and the policy function aims to find a policy that maximizes the value at each state plus the entropy of the policy. The reward for each state-action pair is a function of the change in sum of square error between the estimated path image and the true neuron image plus a term to enforce smoothness.

The branch classifier is used to mark points along the traced path where the neuron branches. When the current path ends, the agent will return to each branch point to continue tracking. The training dataset is created by randomly sampling image windows around the neurons and assigning target labels based on the branch mask. We include random permutations and flips to augment the input data to minimize overfitting and utilized class balancing for generalizability.

Requirements
------------

This code was developed and tested with Python 3.12.8 

Dependencies are listed in requirements.txt

No non-standard hardware is required, but this library uses pytorch which can use gpu acceleration if a gpu is available.

Demo
----

Examples for usage are given in Jupyter notebooks in the notebooks folder of the github repository.

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   installation
   usage
   examples


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
