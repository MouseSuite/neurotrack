Usage
=====
Neurotrack currently includes Python command-line tools to simulate neurons, collect branch point data and train a branch point classification model,\
and train a neuron tracking model.

Command-line tools
******************

simulate_neurons.py
^^^^^^^^^^^^^^^^^^^
Generates and saves simulated neuron images, either from existing neuron swc files or
by generating new simulated neuron trees based on the provided parameters.

To simulate neurons, run the following command from the neurotrack root directory:

.. code-block:: bash

    python bin/simulate_neurons --input <input_file>

The `input` argument is a JSON file listing the following configuration parameters:

    JSON Configuration Parameters
    -----------------------------
    labels_dir : str, optional
        Directory containing SWC files of existing neuron trees. If not provided, neuron trees will be simulated.
    out : str
        Output directory to save the generated neuron images.
    width : int
        Width of the generated neuron images in voxels.
    random_contrast : bool
        Whether to apply random contrast to the neuron images.
    dropout : float
        Density of intensity dropout points for the neuron images.
    random_brightness : bool
        Whether to apply random signal to noise ratio to the neuron images.
    noise : float
        Amount of noise to add to the neuron images.
    binary : bool
        Whether to draw the neuron images as a binary mask.
    seed : int
        Seed for the random number generator.
    count : int, optional
        Number of neuron trees to simulate. Required if `labels_dir` is not provided.
    size : int, optional
        Size of the simulated neuron trees. Required if `labels_dir` is not provided.
    length : int, optional
        Length of the simulated neuron trees. Required if `labels_dir` is not provided.
    stepsize : float, optional
        Step size for the simulated neuron trees. Required if `labels_dir` is not provided.
    uniform_len : bool, optional
        Whether to use uniform length for the simulated neuron trees. Required if `labels_dir` is not provided.
    kappa : float, optional
        Kappa parameter for the simulated neuron trees. Required if `labels_dir` is not provided.
    random_start : bool, optional
        Whether to use random starting points for the simulated neuron trees. Required if `labels_dir` is not provided.
    branches : int, optional
        Number of branches for the simulated neuron trees. Required if `labels_dir` is not provided.

Example input file contents to simulate neuron images from existing SWC files:

.. code-block:: json

    {   
        "labels_dir": "/home/brysongray/data/neuromorpho_sub1",
        "out": "/home/brysongray/data/simulated_neurons/neuromorpho_sub1_with_artifacts",
        "width": 3,
        "noise": 0.05,
        "binary": 0,
        "random_contrast": 1,
        "dropout": 1,
        "random_brightness": 1,
        "seed": 7
    }

Example input file contents to generate neuron images de novo:

.. code-block:: json

    {   
        "out": "/home/brysongray/data/simulated_neurons/3d_no_artifacts_b-1",
        "count": 10,
        "size": 101,
        "length": 20,
        "stepsize": 3.0,
        "width": 3,
        "noise": 0.00,
        "uniform_len": 0,
        "kappa": 20.0,
        "random_start": 1,
        "binary": 0,
        "branches": 0,
        "random_contrast": 0,
        "dropout": 0,
        "random_brightness": 0,
        "seed": 7
    }


collect_branch_data.py
^^^^^^^^^^^^^^^^^^^^^^

Collects neuron image patches and branch labels. Recognizes the following command-line arguments:

    -l, --labels : str
        Path to labels directory (contains swc files).
    -i, --images : str
        Path to images directory.
    -o, --out : str
        Path to output directory.
    -n, --name : str
        Output filename base.
    -a, --adjust : bool
        Set to true if neuron coordinates were rescaled to draw images.
    --n_samples : int
        Number of samples to collect from each image file.


For example:

.. code-block:: bash

    python bin/collect_branch_data --labels /PATH/TO/LABELS/FOLDER --images /PATH/TO/IMAGES/FOLDER --out /PATH/TO/OUTPUTS/FOLDER  --name example_name --adjust --n_samples 50


classifier_train.py
^^^^^^^^^^^^^^^^^^^
Main function to train the branch classifier model. Recognizes the following command-line argumennts:

        -s, --source: Source directory containing labels as csv files and input images folder (observations).
        -o, --out: Path to output directory.
        -l, --learning_rate: Optimizer learning rate.
        -N, --epochs: Number of training epochs.

For example:

.. code-block:: bash

    python bin/classifier_train --source /PATH/TO/SOURCE/FOLDER --out /PATH/TO/OUTPUT/FOLDER --learning_rate 0.001 --epochs 25


sac_train.py
^^^^^^^^^^^^

Main function to train a Soft Actor-Critic (SAC) model for tractography.
This function parses input parameters from a JSON file, initializes the environment,
neural network models, optimizers, and other necessary components, and then trains
the SAC model using the specified parameters.

To run SAC training run the following command from the neurotrack root directory:

.. code-block:: bash

    python bin/sac_train --input <input_file>

The `input` argument is a JSON file listing the following configuration parameters:

    JSON Configuration Parameters
    -----------------------------
    img_path : str
        Path to the input image.
    outdir : str
        Directory to save output results.
    name : str
        Name for the training session.
    step_size : float, optional
        Step size for the environment (default is 1.0).
    step_width : float, optional
        Step width for the environment (default is 1.0).
    batchsize : int, optional
        Batch size for training (default is 256).
    tau : float, optional
        Soft update parameter for target networks (default is 0.005).
    gamma : float, optional
        Discount factor for future rewards (default is 0.99).
    lr : float, optional
        Learning rate for optimizers (default is 0.001).
    alpha : float, optional
        The weight applied to the accuracy component of reward. (default is 1.0).
    beta : float, optional
        The weight applied to the reward prior (default is 1e-3).
    friction : float, optional
        Weight applied to the friction component of reward (default is 1e-4).
    n_episodes : int, optional
        Number of training episodes (default is 100).
    init_temperature : float, optional
        Initial temperature for SAC entropy (default is 0.005).
    target_entropy : float, optional
        Target entropy for SAC (default is 0.0).
    classifier_weights : str, optional
        Path to pre-trained classifier weights.
    sac_weights : str, optional
        Path to pre-trained SAC model weights.

Example input file contents to train the tracking model:

.. code-block:: json

    {
    "img_path": "/home/brysongray/tractography/data_prep/training_data/neuromorpho_with_artifacts",
    "outdir": "/home/brysongray/tractography/sac_training_output_test",
    "name": "neuromorpho_dataset",
    "classifier_weights" : "/home/brysongray/tractography/pretrained_models/neuromorpho_with_artifacts_classifier/resnet_classifier_01-24-25_checkpoint-16.pt",
    "sac_weights": "/home/brysongray/tractography/outputs_test/model_state_dicts_neuromorpho_with_artifacts_01-25-25.pt",
    "n_seeds": 1,
    "step_size": 2.0,
    "step_width": 3.0,
    "batch_size": 256,
    "tau": 0.005,
    "gamma": 0.1,
    "lr": 0.001,
    "alpha": 1.0,
    "beta": 0.2,
    "friction": 0.0,
    "n_episodes": 50,
    "init_temperature": 0.005,
    "target_entropy": 0.0
    }