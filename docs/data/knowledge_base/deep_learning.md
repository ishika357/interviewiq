# Deep Learning Knowledge

## Neural networks and activation functions
A neural network consists of layers of neurons. Each neuron computes a weighted sum of its inputs plus a bias and passes it through an activation function. Activation functions such as ReLU, sigmoid, tanh and softmax add non-linearity; without them, stacked layers would collapse into one linear transformation.

## Backpropagation
Backpropagation computes the gradient of the loss with respect to every weight using the chain rule, moving backwards from the output layer to the input layer. An optimiser such as stochastic gradient descent or Adam uses the gradients and a learning rate to update the weights.

## Vanishing and exploding gradients
In deep networks gradients can shrink towards zero as they are multiplied through many layers, so early layers learn very slowly. Exploding gradients grow very large. Mitigations include ReLU activations, careful weight initialisation, batch normalisation, residual connections, gradient clipping and gated units such as LSTM and GRU.

## Convolutional neural networks
CNNs apply small shared filters that slide over an image to detect local patterns such as edges. Weight sharing greatly reduces parameters compared with fully connected layers and gives translation invariance. Pooling layers reduce spatial size, and deeper layers combine simple features into complex ones.

## Recurrent networks
RNNs process sequences by passing a hidden state from one step to the next. Plain RNNs suffer from vanishing gradients; LSTM and GRU cells use gates to keep long-term information.

## Transformers and self-attention
A transformer uses self-attention instead of recurrence. Each token is projected into a query, key and value vector. Attention weights are computed from scaled dot products between queries and keys, passed through softmax, and used to take a weighted sum of the values. Multi-head attention runs several attention operations in parallel. Transformers process all tokens in parallel and capture long-range dependencies, which made them the basis of modern large language models.

## Regularization in deep learning
Dropout randomly disables neurons during training, early stopping halts training when validation loss stops improving, data augmentation enlarges the dataset and weight decay penalises large weights.
