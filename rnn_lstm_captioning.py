import math
from typing import Optional, Tuple

import torch
import torchvision
from torch import nn
from torch.nn import functional as F
from torchvision.models import feature_extraction

#Original Author: Justin C. Johnson https://web.eecs.umich.edu/~justincj/
#Modified: Jonathan Gryak, Spring 2025

def hello_rnn_lstm_captioning():
    print("Hello from rnn_lstm_captioning.py!")


class ImageEncoder(nn.Module):
    """
    Convolutional network that accepts images as input and outputs their spatial
    grid features. This module serves as the image encoder in the image captioning
    model. We will use a tiny RegNet-X 400MF model that is initialized with
    ImageNet-pretrained weights from Torchvision library.
    See: https://pytorch.org/vision/0.21/models/generated/torchvision.models.regnet_x_400mf.html#torchvision.models.RegNet_X_400MF_Weights

    NOTE: We could use any convolutional network architecture, but we opt for a
    tiny RegNet model so it can train decently with a single K80 Colab GPU.
    """

    def __init__(self, weights=None, verbose: bool = True, device=None, dtype=None):
        """
        Args:
            weights: Whether to initialize this model with pretrained weights
                from Torchvision library.
            verbose: Whether to log expected output shapes during instantiation.
        """
        super().__init__()
        if weights is None:
            self.cnn = torchvision.models.regnet_x_400mf(weights=torchvision.models.RegNet_X_400MF_Weights.IMAGENET1K_V1)
        else:
            self.cnn = torchvision.models.regnet_x_400mf(weights=weights)

        # Move and change dtype if specified
        if device is not None and dtype is not None:
            self.cnn = self.cnn.to(device=device, dtype=dtype)
        elif device is not None:
            self.cnn = self.cnn.to(device=device)
        elif dtype is not None:
            self.cnn = self.cnn.to(dtype=dtype)

        # Torchvision models return global average pooled features by default.
        # Our attention-based models may require spatial grid features. So we
        # wrap the ConvNet with torchvision's feature extractor. We will get
        # the spatial features right before the final classification layer.
        self.backbone = feature_extraction.create_feature_extractor(
            self.cnn, return_nodes={"trunk_output.block4": "c5"}
        )

        # These "c5" features are 1/2^5 = 1/32 the size of the original image

        # Pass a dummy batch of input images to infer output shape.
        dummy_out = self.backbone(torch.randn(2, 3, 224, 224))["c5"]
        self._out_channels = dummy_out.shape[1]

        if verbose:
            print("For input images in NCHW format, shape (2, 3, 224, 224)")
            print(f"Shape of output c5 features: {dummy_out.shape}")

        # Input image batches are expected to be float tensors in range [0, 1].
        # However, the backbone here expects these tensors to be normalized by
        # ImageNet color mean/std (as it was trained that way).
        # We define a function to transform the input images before extraction:
        self.normalize = torchvision.transforms.Normalize(
            mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
        )

    @property
    def out_channels(self):
        """
        Number of output channels in extracted image features. You may access
        this value freely to define more modules to go with this encoder.
        """
        return self._out_channels

    def forward(self, images: torch.Tensor):
        # Input images may be uint8 tensors in [0-255], change them to float
        # tensors in [0-1]. Get float type from backbone (could be float32/64).
        if images.dtype == torch.uint8:
            images = images.to(dtype=self.cnn.stem[0].weight.dtype)
            images /= 255.0

        # Normalize images by ImageNet color mean/std.
        images = self.normalize(images)

        # Extract c5 features from encoder (backbone) and return.
        # shape: (batch_size, out_channels, H / 32, W / 32)
        features = self.backbone(images)["c5"]
        return features


##############################################################################
# Recurrent Neural Network                                                   #
##############################################################################
def rnn_step_forward(x, prev_h, Wx, Wh, b):
    """
    Run the forward pass for a single timestep of a standard RNN that uses a tanh
    activation function.
f
    The input data has dimension D, the hidden state has dimension H, and we use
    a minibatch size of N.

    Args:
        x: Input data for this timestep, of shape (N, D).
        prev_h: Hidden state from previous timestep, of shape (N, H)
        Wx: Weight matrix for input-to-hidden connections, of shape (D, H)
        Wh: Weight matrix for hidden-to-hidden connections, of shape (H, H)
        b: Biases, of shape (H,)

    Returns a tuple of:
        next_h: Next hidden state, of shape (N, H)
        cache: Tuple of values needed for the backward pass.
    """
    next_h, cache = None, None
    hh = torch.mm(x, Wx) + torch.mm(prev_h, Wh) + b
    next_h = torch.tanh(hh)
    cache = Wx, Wh, prev_h, next_h, x
    return next_h, cache


def rnn_step_backward(dnext_h, cache):
    """
    Backward pass for a single timestep of a standard RNN.

    Args:
        dnext_h: Gradient of loss with respect to next hidden state, of shape (N, H)
        cache: Cache object from the forward pass

    Returns a tuple of:
        dx: Gradients of input data, of shape (N, D)
        dprev_h: Gradients of previous hidden state, of shape (N, H)
        dWx: Gradients of input-to-hidden weights, of shape (D, H)
        dWh: Gradients of hidden-to-hidden weights, of shape (H, H)
        db: Gradients of bias vector, of shape (H,)
    """
    dx, dprev_h, dWx, dWh, db = None, None, None, None, None
    Wx, Wh, prev_h, next_h, x = cache
    dn = (1 - next_h ** 2) * dnext_h
    dx = torch.mm(dn, Wx.t())
    dprev_h = torch.mm(dn, Wh.t())
    dWx = torch.mm(x.t(), dn)
    dWh = torch.mm(prev_h.t(), dn)
    db = dn.sum(dim=0)
    return dx, dprev_h, dWx, dWh, db


def rnn_forward(x, h0, Wx, Wh, b):
    """
    Run a standard RNN forward on an entire sequence of data. We assume an input
    sequence composed of T vectors, each of dimension D. The RNN uses a hidden
    size of H, and we work over a minibatch containing N sequences. After running
    the RNN forward, we return the hidden states for all timesteps.

    Args:
        x: Input data for the entire timeseries, of shape (N, T, D).
        h0: Initial hidden state, of shape (N, H)
        Wx: Weight matrix for input-to-hidden connections, of shape (D, H)
        Wh: Weight matrix for hidden-to-hidden connections, of shape (H, H)
        b: Biases, of shape (H,)

    Returns a tuple of:
        h: Hidden states for the entire timeseries, of shape (N, T, H).
        cache: Values needed in the backward pass
    """
    h, cache = None, None
    N, T, D = x.shape
    N, H = h0.shape
    D, H = Wx.shape
    cache = []
    h = torch.zeros((N, T, H), dtype=x.dtype, device=x.device)
    h_ = h0
    for i in range(T):
        h_, c_ = rnn_step_forward(x[:, i, :], h_, Wx, Wh, b)
        cache.append(c_)
        h[:, i, :] = h_[::]
    return h, cache


def rnn_backward(dh, cache):
    """
    Compute the backward pass for a standard RNN over an entire sequence of data.

    Args:
        dh: Upstream gradients of all hidden states, of shape (N, T, H).

    NOTE: 'dh' contains the upstream gradients produced by the
    individual loss functions at each timestep, *not* the gradients
    being passed between timesteps (which you'll have to compute yourself
    by calling rnn_step_backward in a loop).

    Returns a tuple of:
        dx: Gradient of inputs, of shape (N, T, D)
        dh0: Gradient of initial hidden state, of shape (N, H)
        dWx: Gradient of input-to-hidden weights, of shape (D, H)
        dWh: Gradient of hidden-to-hidden weights, of shape (H, H)
        db: Gradient of biases, of shape (H,)
    """
    dx, dh0, dWx, dWh, db = None, None, None, None, None
    to_dh_type = {'dtype': dh.dtype, 'device': dh.device.type}
    N, T, H = dh.shape
    D = cache[-1][-1].shape[1]
    dprev_h = 0
    db = torch.zeros(H, **to_dh_type)
    dWh = torch.zeros(H, H, **to_dh_type)
    dWx = torch.zeros(D, H, **to_dh_type)
    dh0 = torch.zeros(N, H, **to_dh_type)
    dx = torch.zeros(N, T, D, **to_dh_type)
    for t in range(T)[::-1]:
        total_dout = dprev_h + dh[:, t]
        local_dx, dprev_h, local_dWx, local_dWh, local_db = rnn_step_backward(total_dout, cache[t])
        db += local_db
        dWh += local_dWh
        dWx += local_dWx
        dx[:, t] = local_dx
    dh0 = dprev_h
    return dx, dh0, dWx, dWh, db


class RNN(nn.Module):
    """
    Single-layer standard RNN module.

    You don't have to implement anything here but it is highly recommended to
    read through the code as you will implement subsequent modules.
    """

    def __init__(self, input_dim: int, hidden_dim: int):
        """
        Initialize an RNN. Model parameters to initialize:
            Wx: Weight matrix for input-to-hidden connections, of shape (D, H)
            Wh: Weight matrix for hidden-to-hidden connections, of shape (H, H)
            b: Biases, of shape (H,)

        Args:
            input_dim: Input size, denoted as D before
            hidden_dim: Hidden size, denoted as H before
        """
        super().__init__()

        # Register parameters
        self.Wx = nn.Parameter(
            torch.randn(input_dim, hidden_dim).div(math.sqrt(input_dim))
        )
        self.Wh = nn.Parameter(
            torch.randn(hidden_dim, hidden_dim).div(math.sqrt(hidden_dim))
        )
        self.b = nn.Parameter(torch.zeros(hidden_dim))

    def forward(self, x, h0):
        """
        Args:
            x: Input data for the entire timeseries, of shape (N, T, D)
            h0: Initial hidden state, of shape (N, H)

        Returns:
            hn: The hidden state output
        """
        hn, _ = rnn_forward(x, h0, self.Wx, self.Wh, self.b)
        return hn

    def step_forward(self, x, prev_h):
        """
        Args:
            x: Input data for one time step, of shape (N, D)
            prev_h: The previous hidden state, of shape (N, H)

        Returns:
            next_h: The next hidden state, of shape (N, H)
        """
        next_h, _ = rnn_step_forward(x, prev_h, self.Wx, self.Wh, self.b)
        return next_h


class WordEmbedding(nn.Module):
    """
    Simplified version of torch.nn.Embedding.

    We operate on minibatches of size N where
    each sequence has length T. We assume a vocabulary of V words, assigning each
    word to a vector of dimension D.

    Args:
        x: Integer array of shape (N, T) giving indices of words. Each element idx
      of x must be in the range 0 <= idx < V.

    Returns a tuple of:
        out: Array of shape (N, T, D) giving word vectors for all input words.
    """

    def __init__(self, vocab_size: int, embed_size: int):
        super().__init__()

        # Register parameters
        self.W_embed = nn.Parameter(
            torch.randn(vocab_size, embed_size).div(math.sqrt(vocab_size))
        )

    def forward(self, x):

        out = None
        out = self.W_embed[x]
        return out


def temporal_softmax_loss(x, y, ignore_index=None):
    """
    A temporal version of softmax loss for use in RNNs. We assume that we are
    making predictions over a vocabulary of size V for each timestep of a
    timeseries of length T, over a minibatch of size N. The input x gives scores
    for all vocabulary elements at all timesteps, and y gives the indices of the
    ground-truth element at each timestep. We use a cross-entropy loss at each
    timestep, *summing* the loss over all timesteps and *averaging* across the
    minibatch.

    As an additional complication, we may want to ignore the model output at some
    timesteps, since sequences of different length may have been combined into a
    minibatch and padded with NULL tokens. The optional ignore_index argument
    tells us which elements in the caption should not contribute to the loss.

    Args:
        x: Input scores, of shape (N, T, V)
        y: Ground-truth indices, of shape (N, T) where each element is in the
            range 0 <= y[i, t] < V

    Returns a tuple of:
        loss: Scalar giving loss
    """
    loss = None

    loss = torch.nn.functional.cross_entropy(x.reshape(x.shape[0] * x.shape[1], x.shape[2]),
                                             y.reshape(x.shape[0] * x.shape[1]),
                                             ignore_index=ignore_index,
                                             reduction='sum') / x.shape[0]

    return loss


class CaptioningRNN(nn.Module):
    """
    A CaptioningRNN produces captions from images using a recurrent
    neural network.

    The RNN receives input vectors of size D, has a vocab size of V, works on
    sequences of length T, has an RNN hidden dimension of H, uses word vectors
    of dimension W, and operates on minibatches of size N.

    Note that we don't use any regularization for the CaptioningRNN.

    You will implement the `__init__` method for model initialization and
    the `forward` method first, then come back for the `sample` method later.
    """

    def __init__(
        self,
        word_to_idx,
        input_dim: int = 512,
        wordvec_dim: int = 128,
        hidden_dim: int = 128,
        cell_type: str = "rnn",
        image_encoder_weights = None,
        ignore_index: Optional[int] = None,
        device = 'cpu',
        dtype = torch.float32,vocab_size=None):
        """
        Construct a new CaptioningRNN instance.

        Args:
            word_to_idx: A dictionary giving the vocabulary. It contains V
                entries, and maps each string to a unique integer in the
                range [0, V).
            input_dim: Dimension D of input image feature vectors.
            wordvec_dim: Dimension W of word vectors.
            hidden_dim: Dimension H for the hidden state of the RNN.
            cell_type: What type of RNN to use; either 'rnn', 'lstm', or 'attn'.
        """
        super().__init__()
        if cell_type not in {"rnn", "lstm", "attn"}:
            raise ValueError('Invalid cell_type "%s"' % cell_type)

        self.cell_type = cell_type
        self.word_to_idx = word_to_idx
        self.idx_to_word = {i: w for w, i in word_to_idx.items()}

        self.vocab_size = len(word_to_idx)

        self._null = word_to_idx["<NULL>"]
        self._start = word_to_idx.get("<START>", None)
        self._end = word_to_idx.get("<END>", None)
        self.ignore_index = ignore_index

        CNN_H0_Affine_W = torch.randn(hidden_dim, input_dim).div(input_dim ** 0.5)
        CNN_H0_Affine_b = torch.zeros(hidden_dim)
        self.CNN_H0_Affine = nn.Linear(input_dim, hidden_dim)
        self.CNN_H0_Affine.weight.data.copy_(CNN_H0_Affine_W)
        self.CNN_H0_Affine.bias.data.copy_(CNN_H0_Affine_b)

        self.wordEmbedding = WordEmbedding(self.vocab_size, wordvec_dim)

        H_Prob_Affine_W = torch.randn(self.vocab_size, hidden_dim).div(hidden_dim ** 0.5)
        H_Prob_Affine_b = torch.zeros(self.vocab_size)
        self.H_Prob_Affine = nn.Linear(hidden_dim, self.vocab_size)
        self.H_Prob_Affine.weight.data.copy_(H_Prob_Affine_W)
        self.H_Prob_Affine.bias.data.copy_(H_Prob_Affine_b)

        if cell_type == 'rnn':
            self.rnn = RNN(wordvec_dim, hidden_dim)
            self.featureExtractor = ImageEncoder( verbose=True)
        if cell_type == 'lstm':
            self.lstm = LSTM(wordvec_dim, hidden_dim)
            self.featureExtractor = ImageEncoder( verbose=True)
        if cell_type == 'attn':
            Features_A_Affine_W = torch.randn(hidden_dim, input_dim).div(input_dim ** 0.5)
            Features_A_Affine_b = torch.zeros(hidden_dim)
            self.Features_A_Affine = nn.Linear(input_dim, hidden_dim)
            self.Features_A_Affine.weight.data.copy_(Features_A_Affine_W)
            self.Features_A_Affine.bias.data.copy_(Features_A_Affine_b)
            self.attentionLSTM = AttentionLSTM(wordvec_dim, hidden_dim)
            self.featureExtractor = ImageEncoder(verbose=True)


    def forward(self, images, captions):
        """
        Compute training-time loss for the RNN. We input images and the GT
        captions for those images, and use an RNN (or LSTM) to compute loss. The
        backward part will be done by torch.autograd.

        Args:
            images: Input images, of shape (N, 3, 112, 112)
            captions: Ground-truth captions; an integer array of shape (N, T + 1)
                where each element is in the range 0 <= y[i, t] < V

        Returns:
            loss: A scalar loss
        """
        # Cut captions into two pieces: captions_in has everything but the last
        # word and will be input to the RNN; captions_out has everything but the
        # first word and this is what we will expect the RNN to generate. These
        # are offset by one relative to each other because the RNN should produce
        # word (t+1) after receiving word t. The first element of captions_in
        # will be the START token, and the first element of captions_out will
        # be the first word.

        captions_in = captions[:, :-1]
        captions_out = captions[:, 1:]

        loss = 0.0
        features = self.featureExtractor.forward(images)
        h0_A = self.featureProjector(features)
        embed_words = self.wordEmbedding(captions_in)
        hstates = self.coreNetwork(embed_words, h0_A)
        scores = self.outProjector(hstates)
        loss = temporal_softmax_loss(scores, captions_out, ignore_index=self._null)

        return loss

    def sample(self, images, max_length=15):
        """
        Run a test-time forward pass for the model, sampling captions for input
        feature vectors.

        At each timestep, we embed the current word, pass it and the previous hidden
        state to the RNN to get the next hidden state, use the hidden state to get
        scores for all vocab words, and choose the word with the highest score as
        the next word. The initial hidden state is computed by applying an affine
        transform to the image features, and the initial word is the <START>
        token.

        For LSTMs you will also have to keep track of the cell state; in that case
        the initial cell state should be zero.

        Args:
            images: Input images, of shape (N, 3, 112, 112)
            max_length: Maximum length T of generated captions

        Returns:
            captions: Array of shape (N, max_length) giving sampled captions,
                where each element is an integer in the range [0, V). The first
                element of captions should be the first sampled word, not the
                <START> token.
        """
       # Extract features from the input images.
        features = self.featureExtractor.extract_mobilenet_feature(images)

        # Get the device on which we are operating (CPU or GPU [CUDA]).
        device = features.device
        # Put "captions" to the actual device, as all other tensors are in this device.
        captions = captions.to(device=device)

        # Use an affine transformation.
        if self.cell_type in ['rnn', 'lstm']:
          # Initialize the hidden state by applying the affine transform to the features.
          h = self.featureProjector(features)
          # For LSTM: Initialize the cell hidden state with a zeroes-matrix of 'h' shape.
          # If a RNN is used (istead of LSTM), then "c" will simply not be used.
          c = torch.zeros_like(h, device=device)
        else: # "cell_type" is 'attention'.
          # Put "attn_weights_all" to the actual device, as all other tensors are in this device.
          attn_weights_all = attn_weights_all.to(device=device)
          # Project the features to the the projected CNN activation input.
          A = self.featureProjector(features)
          # For AttentionLSTM: initial hidden state and cell state would both be A.mean(dim=(2, 3)).
          h, c = A.mean(dim=(2, 3)), A.mean(dim=(2, 3))

        # Initialize the words feeded to the RNN (for each minibatch sample) with the
        # <START> token.
        fwords = self._start
        # Initialize the encounter mark of the <END> token for each minibatch sample.
        # In the beginning, for each minibatch sample, the <END> token is not encountered,
        # thus, 'True' value is assigned for each minibatch sample. This will:
        # - Stop adding tokens for minibatch samples which have already encountered the <END>.
        # - Stop generating the tokens for all minibatch samples *if and only if* all the
        # minibatch samples have already encountered the <END> token.
        notend = torch.full([N], True, device=device)

        # Start generating tokens for each minibatch sample.
        # One token (per sample) per timestep (ts).
        for ts in range(max_length):
          # Embed the word (for each sample) using the learned word embeddings.
          x = self.wordEmbedding(fwords)
          # Apply the RNN/LSTM forward step. Output is the next hidden state (h).
          if self.cell_type == 'rnn':
            h = self.coreNetwork.step_forward(x, h)
          elif self.cell_type == 'lstm':
            h, c = self.coreNetwork.step_forward(x, h, c)
          else: # "cell_type" is 'attention'.
            attn, attn_weights = dot_product_attention(h, A)
            # Save current timestep attention weights (for visualization purpose).
            attn_weights_all[:, ts] = attn_weights
            h, c = self.coreNetwork.step_forward(x, h, c, attn)

          # Reshape "h" to fit the temporal affine forward pass, since the latter is applied
          # to the current timestep 'h' only (and not to the whole timesteps 'h' as it was
          # designed to).
          # Reshape "h" from (N, D) to (N, T, D), where T=1.
          hts = h.unsqueeze(1)
          # Apply the temporal affine forward pass on the "hidden state for the current
          # timestep" (hts).
          temp = self.outProjector(hts)
          # Reshape 'temp' from (N, 1, M) to (N, M).
          temp = temp.squeeze()

          # Select the word (for each sample) with the highest score.
          fwords = torch.argmax(temp, axis=1)

          # Check if the <END> token is encountered for each sample. If so, mark it.
          mask = fwords == self._end
          notend[mask] = False
          # Check if all the samples have already encountered the <END> token.
          # If so, stop generating tokens (exit the loop).
          if not notend.any():
            break

          # Add current timestep generated word (for each sample) to the caption.
          # If the <END> token has not been already encountered.
          captions[notend, ts] = fwords[notend]

        ############################################################################
        #                             END OF YOUR CODE                             #
        ############################################################################
        if self.cell_type == 'attention':
          return captions, attn_weights_all.cpu()
        else:
          return captions



class LSTM(nn.Module):
    """Single-layer, uni-directional LSTM module."""

    def __init__(self, input_dim: int, hidden_dim: int):
        """
        Initialize a LSTM. Model parameters to initialize:
            Wx: Weights for input-to-hidden connections, of shape (D, 4H)
            Wh: Weights for hidden-to-hidden connections, of shape (H, 4H)
            b: Biases, of shape (4H,)

        Args:
            input_dim: Input size, denoted as D before
            hidden_dim: Hidden size, denoted as H before
        """
        super().__init__()

        # Register parameters
        self.Wx = nn.Parameter(
            torch.randn(input_dim, hidden_dim * 4).div(math.sqrt(input_dim))
        )
        self.Wh = nn.Parameter(
            torch.randn(hidden_dim, hidden_dim * 4).div(math.sqrt(hidden_dim))
        )
        self.b = nn.Parameter(torch.zeros(hidden_dim * 4))

    def step_forward(
        self, x: torch.Tensor, prev_h: torch.Tensor, prev_c: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass for a single timestep of an LSTM.
        The input data has dimension D, the hidden state has dimension H, and
        we use a minibatch size of N.

        Args:
            x: Input data for one time step, of shape (N, D)
            prev_h: The previous hidden state, of shape (N, H)
            prev_c: The previous cell state, of shape (N, H)
            Wx: Input-to-hidden weights, of shape (D, 4H)
            Wh: Hidden-to-hidden weights, of shape (H, 4H)
            b: Biases, of shape (4H,)

        Returns:
            Tuple[torch.Tensor, torch.Tensor]
                next_h: Next hidden state, of shape (N, H)
                next_c: Next cell state, of shape (N, H)
        """

        next_h, next_c = None, None
        H = prev_h.shape[1]
        a = x.mm(self.Wx) + prev_h.mm(self.Wh) + self.b
        a_i = a[:, 0 * H:1 * H]
        a_f = a[:, 1 * H:2 * H]
        a_o = a[:, 2 * H:3 * H]
        a_g = a[:, 3 * H:4 * H]

        i = torch.sigmoid(a_i)
        f = torch.sigmoid(a_f)
        o = torch.sigmoid(a_o)
        g = torch.tanh(a_g)

        next_c = f * prev_c + i * g
        next_h = o * torch.tanh(next_c)
        return next_h, next_c

    def forward(self, x: torch.Tensor, h0: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for an LSTM over an entire sequence of data. We assume an
        input sequence composed of T vectors, each of dimension D. The LSTM
        uses a hidden size of H, and we work over a minibatch containing N
        sequences. After running the LSTM forward, we return the hidden states
        for all timesteps.

        Note that the initial cell state is passed as input, but the initial
        cell state is set to zero. Also note that the cell state is not returned;
        it is an internal variable to the LSTM and is not accessed from outside.

        Args:
            x: Input data for the entire timeseries, of shape (N, T, D)
            h0: Initial hidden state, of shape (N, H)

        Returns:
            hn: The hidden state output.
        """

        c0 = torch.zeros_like(
            h0
        )  # we provide the initial cell state c0 here for you!

        hn = None
        N, T, D = x.shape
        H = h0.shape[1]
        hn = torch.zeros([N, T, H]).to(h0.device).to(h0.dtype)
        for t in range(T):
            if t == 0:
                hn[:, t, :], c = self.step_forward(x[:, t, :], h0.clone(), c0)
            else:
                hn[:, t, :], c = self.step_forward(x[:, t, :], hn[:, t - 1, :].clone(), c)

        return hn


def dot_product_attention(prev_h, A):
    """
    A simple scaled dot-product attention layer.

    Args:
        prev_h: The LSTM hidden state from previous time step, of shape (N, H)
        A: **Projected** CNN feature activation, of shape (N, H, 4, 4),
         where H is the LSTM hidden state size

    Returns:
        attn: Attention embedding output, of shape (N, H)
        attn_weights: Attention weights, of shape (N, 4, 4)

    """
    N, H, D_a, _ = A.shape

    attn, attn_weights = None, None
    Mt = torch.matmul(prev_h.view(N, 1, H), A.view(N, H, 4 * 4)).squeeze(1).div(H ** 0.5)
    attn_weights = F.softmax(Mt, dim=1)
    attn = torch.matmul(A.view(N, H, 4 * 4), attn_weights.view(N, 4 * 4, 1)).squeeze(2)
    attn_weights = attn_weights.view(N, 4, 4)

    return attn, attn_weights


class AttentionLSTM(nn.Module):
    """
    This is our single-layer, uni-directional Attention module.

    Args:
        input_dim: Input size, denoted as D before
        hidden_dim: Hidden size, denoted as H before
    """

    def __init__(self, input_dim: int, hidden_dim: int):
        """
        Initialize a LSTM. Model parameters to initialize:
            Wx: Weights for input-to-hidden connections, of shape (D, 4H)
            Wh: Weights for hidden-to-hidden connections, of shape (H, 4H)
            Wattn: Weights for attention-to-hidden connections, of shape (H, 4H)
            b: Biases, of shape (4H,)
        """
        super().__init__()

        # Register parameters
        self.Wx = nn.Parameter(
            torch.randn(input_dim, hidden_dim * 4).div(math.sqrt(input_dim))
        )
        self.Wh = nn.Parameter(
            torch.randn(hidden_dim, hidden_dim * 4).div(math.sqrt(hidden_dim))
        )
        self.Wattn = nn.Parameter(
            torch.randn(hidden_dim, hidden_dim * 4).div(math.sqrt(hidden_dim))
        )
        self.b = nn.Parameter(torch.zeros(hidden_dim * 4))

    def step_forward(
        self,
        x: torch.Tensor,
        prev_h: torch.Tensor,
        prev_c: torch.Tensor,
        attn: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input data for one time step, of shape (N, D)
            prev_h: The previous hidden state, of shape (N, H)
            prev_c: The previous cell state, of shape (N, H)
            attn: The attention embedding, of shape (N, H)

        Returns:
            next_h: The next hidden state, of shape (N, H)
            next_c: The next cell state, of shape (N, H)
        """


        next_h, next_c = None, None
        H = prev_h.shape[1]
        a = x.mm(self.Wx) + prev_h.mm(self.Wh) + attn.mm(self.Wattn) + self.b
        a_i = a[:, 0 * H:1 * H]
        a_f = a[:, 1 * H:2 * H]
        a_o = a[:, 2 * H:3 * H]
        a_g = a[:, 3 * H:4 * H]

        i = torch.sigmoid(a_i)
        f = torch.sigmoid(a_f)
        o = torch.sigmoid(a_o)
        g = torch.tanh(a_g)

        next_c = f * prev_c + i * g
        next_h = o * torch.tanh(next_c)
        return next_h, next_c

    def forward(self, x: torch.Tensor, A: torch.Tensor):
        """
        Forward pass for an LSTM over an entire sequence of data. We assume an
        input sequence composed of T vectors, each of dimension D. The LSTM uses
        a hidden size of H, and we work over a minibatch containing N sequences.
        After running the LSTM forward, we return hidden states for all timesteps.

        Note that the initial cell state is passed as input, but the initial cell
        state is set to zero. Also note that the cell state is not returned; it
        is an internal variable to the LSTM and is not accessed from outside.

        h0 and c0 are same initialized as the global image feature (meanpooled A)
        For simplicity, we implement scaled dot-product attention, which means in
        Eq. 4 of the paper (https://arxiv.org/pdf/1502.03044.pdf),
        f_{att}(a_i, h_{t-1}) equals to the scaled dot product of a_i and h_{t-1}.

        Args:
            x: Input data for the entire timeseries, of shape (N, T, D)
            A: The projected CNN feature activation, of shape (N, H, 4, 4)

        Returns:
            hn: The hidden state output
        """

        # The initial hidden state h0 and cell state c0 are initialized
        # differently in AttentionLSTM from the original LSTM and hence
        # we provided them for you.
        h0 = A.mean(dim=(2, 3))  # Initial hidden state, of shape (N, H)
        c0 = h0  # Initial cell state, of shape (N, H)

        hn = None
        N, T, D = x.shape
        _, H = h0.shape
        hn = torch.zeros([N, T, H]).to(h0.device).to(h0.dtype)
        prev_h = h0
        prev_c = c0
        attn, attn_weights = dot_product_attention(prev_h, A)
        for t in range(T):
            prev_h, prev_c = self.step_forward(x[:, t], prev_h, prev_c, attn)
            attn, attn_weights = dot_product_attention(prev_h, A)
            hn[:, t] = prev_h
        return hn
