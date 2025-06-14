"""
This file runs many different experiments and is very dirty.
Main things:
- Find a way to shift (all instances of) a word to a new word by modifying the sequence embedding
- Check that if we change the decoder to a different language the shifted meaning is retained
- A bunch of experiments about positions, we see that the sequence embedding does encode the positional information
although it's not so easy to directly use this to tweak positions. this is done with filler tokens, depending on the filler token
the pattern changes, meaning that in real sentences it would be tricky, i.e. no obvious general vector to refer to a given position
or a given position 1 to position 2 mapping.

todo clean this up and split in to different files
"""

# %%
import os
import random
import sys

import numpy as np
import torch

# --- Configuration ---
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
RANDOM_STATE = 42
# Seed for reproducibility
random.seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)
torch.manual_seed(RANDOM_STATE)
if DEVICE.type == "cuda":
    torch.cuda.manual_seed_all(RANDOM_STATE)

# %%

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.sonar_encoder_decoder import SonarEncoderDecoder

# %%
encoder_decoder = SonarEncoderDecoder(device="cuda")

# %%
unk_token_id = encoder_decoder.tokenizer.vocab_info.unk_idx
house_id = encoder_decoder.get_vocab_id("house")
dog_id = encoder_decoder.get_vocab_id("dog")
sentence_embeddings, encoded_seqs = encoder_decoder.encode(
    torch.cat(
        [
            encoder_decoder.list_str_to_token_ids_batch(
                # [
                #     ["dog", "dog"],
                #     ["house", "house"],
                #     ["car", "car"],
                #     ["cat", "cat"],
                #     ["dog", "house"],
                #     ["house", "dog"],
                # ]
                [
                    ["_", "_", "dog"],
                    ["_", "dog", "_"],
                    ["dog", "_", "_"],
                    ["_", "_", "cat"],
                    ["_", "cat", "_"],
                    ["cat", "_", "_"],
                ]
            ),
        ]
    )
)
sentence_embeddings, encoded_seqs
# %%

greedy_token_ids = encoder_decoder.decode(sentence_embeddings)
greedy_token_ids
# %%
encoder_decoder.token_ids_to_list_str_batch(greedy_token_ids)
# %%
encoder_decoder.decode(sentence_embeddings)

# %%
encoder_decoder.token_ids_to_list_str_batch(encoder_decoder.decode(sentence_embeddings))
# %%
sentence_embeddings
# %%
import pandas as pd
from sklearn.decomposition import PCA

# Perform PCA on sentence embeddings
pca = PCA(n_components=2)
embeddings_2d = pca.fit_transform(sentence_embeddings.detach().cpu().numpy())

# Create scatter plot with plotly
import plotly.express as px

# Create a DataFrame with the PCA components and labels
df = pd.DataFrame(
    {
        "PCA1": embeddings_2d[:, 0],
        "PCA2": embeddings_2d[:, 1],
        "Word": [
            "_ _ dog",
            "_ dog _",
            "dog _ _",
            "_ _ cat",
            "_ cat _",
            "cat _ _",
        ],  # Labels from the original input
    }
)

# Create interactive scatter plot
fig = px.scatter(
    df, x="PCA1", y="PCA2", text="Word", title="2D PCA Visualization of Word Embeddings"
)
fig.update_traces(textposition="top center")
fig.show()

# %%
dog_to_cat = sentence_embeddings[3] - sentence_embeddings[0]
cat_from_dog = sentence_embeddings[1] + dog_to_cat
# %%
# Create DataFrame with original points and the new transformed point
df_with_transform = pd.DataFrame(
    {
        "PCA1": np.append(
            embeddings_2d[:, 0],
            pca.transform(cat_from_dog.detach().cpu().numpy().reshape(1, -1))[0, 0],
        ),
        "PCA2": np.append(
            embeddings_2d[:, 1],
            pca.transform(cat_from_dog.detach().cpu().numpy().reshape(1, -1))[0, 1],
        ),
        "Word": [
            "_ _ dog",
            "_ dog _",
            "dog _ _",
            "_ _ cat",
            "_ cat _",
            "cat _ _",
            "cat from _ dog _",
        ],
    }
)

# Create interactive scatter plot with both original and transformed points
fig = px.scatter(
    df_with_transform,
    x="PCA1",
    y="PCA2",
    text="Word",
    title="2D PCA Visualization of Word Embeddings with Transformed Point",
)
fig.update_traces(textposition="top center")
fig.show()

# %%
encoder_decoder.token_ids_to_list_str_batch(encoder_decoder.decode(sentence_embeddings))

# %%
encoder_decoder.token_ids_to_list_str_batch(
    encoder_decoder.decode(cat_from_dog.unsqueeze(0))
)

# %%
sequence_embeddings = {}
for sequence in [
    ("cat",),
    ("dog",),
    ("_", "_", "dog"),
    ("_", "dog", "_"),
    ("dog", "_", "_"),
    ("_", "_", "cat"),
    ("_", "cat", "_"),
    ("cat", "_", "_"),
]:
    sentence_embeddings, encoded_seqs = encoder_decoder.encode(
        torch.cat(
            [
                encoder_decoder.list_str_to_token_ids_batch([sequence]),
            ]
        )
    )
    sequence_embeddings[sequence] = {
        "sequence_embeddings": sentence_embeddings,
        "decoded": encoder_decoder.token_ids_to_list_str_batch(
            encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
        ),
    }
sequence_embeddings
# %%
dog_to_cat = (
    sequence_embeddings[("cat",)]["sequence_embeddings"]
    - sequence_embeddings[("dog",)]["sequence_embeddings"]
)
# %%
sequence_embeddings[("cat",)]["decoded"]

# %%
# Create transformed dog sequences by adding dog_to_cat vector
transformed_sequences = {}
for sequence, embedding_dict in sequence_embeddings.items():
    if "dog" in sequence:
        transformed_embedding = embedding_dict["sequence_embeddings"] + dog_to_cat
        transformed_sequences[sequence + ("transformed",)] = {
            "sequence_embeddings": transformed_embedding,
            "decoded": encoder_decoder.token_ids_to_list_str_batch(
                encoder_decoder.decode(transformed_embedding.unsqueeze(0))
            ),
        }
    # The cat sequences are already in sequence_embeddings and will be included
    # when we merge the dictionaries below with {**sequence_embeddings, **transformed_sequences}
    # We only need transformed_sequences to hold the transformed dog sequences

# Combine original and transformed embeddings
all_sequences = {**sequence_embeddings, **transformed_sequences}

# Prepare data for PCA
embeddings_matrix = torch.stack(
    [seq_dict["sequence_embeddings"] for seq_dict in all_sequences.values()]
)
sequence_labels = [" ".join(seq) for seq in all_sequences.keys()]

# Reshape embeddings matrix to 2D before PCA
embeddings_matrix_2d = embeddings_matrix.reshape(embeddings_matrix.shape[0], -1)

# Perform PCA
pca = PCA(n_components=2)
embeddings_2d = pca.fit_transform(embeddings_matrix_2d.cpu().detach().numpy())

# Create DataFrame for plotting
df_all = pd.DataFrame(
    {
        "PCA1": embeddings_2d[:, 0],
        "PCA2": embeddings_2d[:, 1],
        "Sequence": sequence_labels,
    }
)

# Create scatter plot
fig = px.scatter(
    df_all,
    x="PCA1",
    y="PCA2",
    text="Sequence",
    title="2D PCA Visualization of Original and Transformed Sequences",
)
fig.update_traces(textposition="top center")
fig.show()

# %%
transformed_sequences
# %%
sequence_embeddings = {}
for sequence in [
    ("the", "dog", "was", "happy"),
    ("the", "dog", "was", "sad"),
    ("there", "was", "a", "dog"),
    ("dog", "is", "my", "name"),
    ("is", "the", "dog", "house"),
    ("is", "the", "dog", "happy"),
    ("the", "dog", "saw", "dog"),
    ("dog", "and", "dog", "played"),
    ("my", "dog", "likes", "dog"),
    ("dog", "sees", "another", "dog"),
    ("dog", "met", "the", "dog"),
    ("the", "cat", "saw", "dog"),
    ("cat", "and", "dog", "played"),
    ("my", "cat", "likes", "dog"),
    ("cat", "sees", "another", "dog"),
    ("dog", "met", "the", "cat"),
    ("dog", "dog", "dog", "dog"),
    ("cat", "cat", "cat", "cat"),
]:
    sentence_embeddings, encoded_seqs = encoder_decoder.encode(
        torch.cat(
            [
                encoder_decoder.list_str_to_token_ids_batch([sequence]),
            ]
        )
    )
    sequence_embeddings[sequence] = {
        "sequence_embeddings": sentence_embeddings,
        "decoded": encoder_decoder.token_ids_to_list_str_batch(
            encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
        ),
    }
sequence_embeddings
# %%
# Get embeddings for original and transformed sequences
all_embeddings = []
sequence_labels = []

for sequence in sequence_embeddings.keys():
    # Original sequence embeddings
    orig_embedding = sequence_embeddings[sequence]["sequence_embeddings"]
    all_embeddings.append(orig_embedding.detach())
    sequence_labels.append(" ".join(sequence))

    # Transform sequence and get embeddings
    transformed_sequence = list(sequence)
    for i, word in enumerate(transformed_sequence):
        if word == "dog":
            transformed_sequence[i] = "cat"

    transformed_embeddings, _ = encoder_decoder.encode(
        torch.cat([encoder_decoder.list_str_to_token_ids_batch([transformed_sequence])])
    )
    all_embeddings.append(transformed_embeddings.detach())
    sequence_labels.append(" ".join(transformed_sequence))

# Stack all embeddings
embeddings_matrix = torch.stack(all_embeddings)

# Reshape embeddings matrix to 2D before PCA
embeddings_matrix_2d = embeddings_matrix.reshape(embeddings_matrix.shape[0], -1)

# Apply PCA
pca = PCA(n_components=3)  # Changed to 3 components
embeddings_3d = pca.fit_transform(embeddings_matrix_2d.cpu().numpy())

# Create DataFrame for plotting
df = pd.DataFrame(
    {
        "PCA1": embeddings_3d[:, 0],
        "PCA2": embeddings_3d[:, 1],
        "PCA3": embeddings_3d[:, 2],  # Added third component
        "Sequence": sequence_labels,
        "Type": [
            "Original" if i % 2 == 0 else "Transformed"
            for i in range(len(sequence_labels))
        ],
    }
)

# Create 3D scatter plot
fig = px.scatter_3d(
    df,
    x="PCA1",
    y="PCA2",
    z="PCA3",  # Added z dimension
    text="Sequence",
    color="Type",
    title="3D PCA Visualization of Original vs Dog->Cat Transformed Sequences",
)
fig.update_traces(textposition="top center")

# Enable zoom by updating layout
fig.update_layout(
    scene=dict(
        dragmode="orbit",
        camera=dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=0),
            eye=dict(x=1.5, y=1.5, z=1.5),
        ),
    )
)

fig.show()

# %%
# Decode the transformed embeddings back to text
decoded_sequences = []
for i in range(0, len(all_embeddings), 2):
    # Get original and transformed embeddings
    orig_emb = all_embeddings[i]
    trans_emb = all_embeddings[i + 1]

    # Decode both embeddings
    orig_decoded = encoder_decoder.decode(orig_emb.unsqueeze(0))
    trans_decoded = encoder_decoder.decode(trans_emb.unsqueeze(0))

    # Convert token IDs to strings
    orig_tokens = encoder_decoder.token_ids_to_list_str(orig_decoded[0])
    trans_tokens = encoder_decoder.token_ids_to_list_str(trans_decoded[0])

    # Add to list
    decoded_sequences.append({"Original": orig_tokens, "Transformed": trans_tokens})

# Print decoded sequences
print("\nDecoded Sequences:")
print("-" * 50)
for i, seq in enumerate(decoded_sequences):
    print(f"\nSequence pair {i + 1}:")
    print(f"Original:    {seq['Original']}")
    print(f"Transformed: {seq['Transformed']}")


# %%
encoder_decoder_spanish_to_spanish = SonarEncoderDecoder(
    device="cuda", decoder_language="spa_Latn"
)
# Decode the transformed embeddings back to text
decoded_sequences = []
for i in range(0, len(all_embeddings), 2):
    # Get original and transformed embeddings
    orig_emb = all_embeddings[i]
    trans_emb = all_embeddings[i + 1]

    # Decode both embeddings
    orig_decoded = encoder_decoder_spanish_to_spanish.decode(orig_emb.unsqueeze(0))
    trans_decoded = encoder_decoder_spanish_to_spanish.decode(trans_emb.unsqueeze(0))

    # Convert token IDs to strings
    orig_tokens = encoder_decoder_spanish_to_spanish.token_ids_to_list_str(
        orig_decoded[0]
    )
    trans_tokens = encoder_decoder_spanish_to_spanish.token_ids_to_list_str(
        trans_decoded[0]
    )

    # Add to list
    decoded_sequences.append({"Original": orig_tokens, "Transformed": trans_tokens})

# Print decoded sequences
print("\nDecoded Sequences:")
print("-" * 50)
for i, seq in enumerate(decoded_sequences):
    print(f"\nSequence pair {i + 1}:")
    print(f"Original:    {seq['Original']}")
    print(f"Transformed: {seq['Transformed']}")
# %%
# sequence_embeddings = {}
# for sequence in [
#     "thewolf",
#     "germanshepherd",
#     "goldenretriever",
#     "thefox",
# ]:
#     sentence_embeddings, encoded_seqs = encoder_decoder.encode(
#         torch.cat(
#             [
#                 encoder_decoder.list_str_to_token_ids_batch([sequence]),
#             ]
#         )
#     )
#     sequence_embeddings[sequence] = {
#         "sequence_embeddings": sentence_embeddings,
#         "decoded": encoder_decoder.token_ids_to_list_str_batch(
#             encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
#         ),
#     }
# sequence_embeddings
# # %%
# # Apply transformation to each sequence
# print("\nApplying dog->cat transformation vector to sequences:")
# print("-" * 50)
# for sequence, data in sequence_embeddings.items():
#     # Get original embedding
#     orig_embedding = data["sequence_embeddings"]

#     # Apply transformation
#     transformed_embedding = orig_embedding + dog_to_cat

#     # Decode both original and transformed
#     orig_decoded = encoder_decoder.token_ids_to_list_str_batch(
#         encoder_decoder.decode(orig_embedding.unsqueeze(0))
#     )
#     trans_decoded = encoder_decoder.token_ids_to_list_str_batch(
#         encoder_decoder.decode(transformed_embedding.unsqueeze(0))
#     )

#     # print(f"\nOriginal sequence: {sequence}")
#     print(f"Original decoded:  {orig_decoded}")
#     print(f"Transformed decoded: {trans_decoded}")

# # %%
sequence_embeddings = {}
for sequence in [
    ("cat", "cat"),
    ("dog", "dog"),
    ("cat", "dog"),
    ("dog", "cat"),
]:
    sentence_embeddings, encoded_seqs = encoder_decoder.encode(
        torch.cat(
            [
                encoder_decoder.list_str_to_token_ids_batch([sequence]),
            ]
        )
    )
    sequence_embeddings[sequence] = {
        "sequence_embeddings": sentence_embeddings,
        "decoded": encoder_decoder.token_ids_to_list_str_batch(
            encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
        ),
    }
sequence_embeddings
# # %%
dog_dog_to_cat_cat = (
    sequence_embeddings[("cat", "cat")]["sequence_embeddings"]
    - sequence_embeddings[("dog", "dog")]["sequence_embeddings"]
)
cat_dog_to_cat_cat = (
    sequence_embeddings[("cat", "cat")]["sequence_embeddings"]
    - sequence_embeddings[("cat", "dog")]["sequence_embeddings"]
)
dog_cat_to_cat_cat = (
    sequence_embeddings[("cat", "cat")]["sequence_embeddings"]
    - sequence_embeddings[("dog", "cat")]["sequence_embeddings"]
)
dog_dog_to_cat_dog = (
    sequence_embeddings[("cat", "dog")]["sequence_embeddings"]
    - sequence_embeddings[("dog", "dog")]["sequence_embeddings"]
)
dog_dog_to_dog_cat = (
    sequence_embeddings[("dog", "cat")]["sequence_embeddings"]
    - sequence_embeddings[("dog", "dog")]["sequence_embeddings"]
)
dog_cat_to_cat_dog = (
    sequence_embeddings[("cat", "dog")]["sequence_embeddings"]
    - sequence_embeddings[("dog", "cat")]["sequence_embeddings"]
)
cat_dog_to_dog_cat = (
    sequence_embeddings[("dog", "cat")]["sequence_embeddings"]
    - sequence_embeddings[("cat", "dog")]["sequence_embeddings"]
)


# %%

# Stack all vectors and perform PCA
all_vectors = torch.stack(
    [
        dog_dog_to_cat_cat,
        cat_dog_to_cat_cat,
        dog_cat_to_cat_cat,
        dog_dog_to_cat_dog,
        dog_dog_to_dog_cat,
        dog_cat_to_cat_dog,
        cat_dog_to_dog_cat,
    ]
)

# Reshape to 2D before PCA
all_vectors = all_vectors.view(all_vectors.size(0), -1)

import numpy as np
import plotly.graph_objects as go
from sklearn.decomposition import PCA

# Perform PCA
pca = PCA(n_components=3)
vectors_3d = pca.fit_transform(all_vectors.cpu().detach().numpy())

# Create figure
fig = go.Figure()

# Plot each vector as an arrow
vector_names = [
    "dog,dog→cat,cat",
    "cat,dog→cat,cat",
    "dog,cat→cat,cat",
    "dog,dog→cat,dog",
    "dog,dog→dog,cat",
    "dog,cat→cat,dog",
    "cat,dog→dog,cat",
]

colors = ["red", "blue", "green", "purple", "orange", "cyan", "magenta"]

for i, (vector, name, color) in enumerate(zip(vectors_3d, vector_names, colors)):
    # Add arrow
    fig.add_trace(
        go.Scatter3d(
            x=[0, vector[0]],
            y=[0, vector[1]],
            z=[0, vector[2]],
            mode="lines+text",
            line=dict(color=color, width=5),
            text=["", name],
            textposition="top center",
            name=name,
            showlegend=True,
        )
    )

# Update layout
fig.update_layout(
    scene=dict(
        xaxis_title="PC1",
        yaxis_title="PC2",
        zaxis_title="PC3",
        camera=dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=0),
            eye=dict(x=1.5, y=1.5, z=1.5),
        ),
    ),
    showlegend=True,
    title="PCA Visualization of Token Transformation Vectors",
)

fig.show()


# %%
# Create figure for positions
fig = go.Figure()

# Get embeddings for all combinations of cat and dog
sequences = [
    ("cat", "cat"),
    ("cat", "dog"),
    ("dog", "cat"),
    ("dog", "dog"),
    ("cat",),
    ("dog",),
]

positions = []
for seq in sequences:
    sentence_embeddings, _ = encoder_decoder.encode(
        torch.cat([encoder_decoder.list_str_to_token_ids_batch([seq])])
    )
    positions.append(sentence_embeddings.cpu().detach().numpy())

# Convert to numpy array and apply PCA
positions_array = np.vstack(positions)
pca = PCA(n_components=3)
positions_3d = pca.fit_transform(positions_array)

# Plot each position
colors = ["red", "blue", "green", "purple", "orange", "cyan"]

for i, (pos, seq, color) in enumerate(zip(positions_3d, sequences, colors)):
    # Add point
    name = ",".join(seq)
    fig.add_trace(
        go.Scatter3d(
            x=[pos[0]],
            y=[pos[1]],
            z=[pos[2]],
            mode="markers+text",
            marker=dict(size=10, color=color),
            text=[name],
            textposition="top center",
            name=name,
            showlegend=True,
        )
    )

# Update layout
fig.update_layout(
    scene=dict(
        xaxis_title="PC1",
        yaxis_title="PC2",
        zaxis_title="PC3",
        camera=dict(
            up=dict(x=0, y=0, z=1),
            center=dict(x=0, y=0, z=0),
            eye=dict(x=1.5, y=1.5, z=1.5),
        ),
    ),
    showlegend=True,
    title="PCA Visualization of Token Position Embeddings",
)

fig.show()

# %%
# Get vector from "cat" to "cat,cat"
# Need to first get embeddings for single "cat" token
sequence_embeddings_single = {}
for sequence in [("cat",)]:
    sentence_embeddings, encoded_seqs = encoder_decoder.encode(
        torch.cat(
            [
                encoder_decoder.list_str_to_token_ids_batch([sequence]),
            ]
        )
    )
    sequence_embeddings_single[sequence] = {
        "sequence_embeddings": sentence_embeddings,
        "decoded": encoder_decoder.token_ids_to_list_str_batch(
            encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
        ),
    }

cat_to_cat_cat = (
    sequence_embeddings[("cat", "cat")]["sequence_embeddings"]
    - sequence_embeddings_single[("cat",)]["sequence_embeddings"]
)
cat_to_cat_cat

# %%
# Define a list of single tokens
single_tokens = [
    ("dog",),
    ("house",),
    ("tree",),
    ("car",),
    ("book",),
    ("bird",),
    ("fish",),
    ("table",),
    ("chair",),
    ("phone",),
    ("dog", "dog"),
    ("house", "house"),
    ("tree", "tree"),
    ("car", "car"),
    ("book", "book"),
    ("bird", "bird"),
    ("fish", "fish"),
    ("table", "table"),
    ("chair", "chair"),
    ("phone", "phone"),
    ("dog", "house"),
    ("dog", "bird"),
    ("house", "tree"),
    ("car", "book"),
    ("bird", "fish"),
    ("table", "chair"),
    ("phone", "car"),
    ("tree", "phone"),
    ("book", "table"),
    ("fish", "dog"),
]

# Get embeddings for each token
test_embeddings = {}
for sequence in single_tokens:
    sentence_embeddings, encoded_seqs = encoder_decoder.encode(
        torch.cat(
            [
                encoder_decoder.list_str_to_token_ids_batch([sequence]),
            ]
        )
    )
    test_embeddings[sequence] = {
        "sequence_embeddings": sentence_embeddings,
        "decoded": encoder_decoder.token_ids_to_list_str_batch(
            encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
        ),
    }

# Apply the cat_to_cat_cat transformation and decode
print("\nApplying 'cat->cat,cat' transformation to single tokens:")
print("-" * 50)
# Store results in a list
results = []
for sequence, data in test_embeddings.items():
    # Get original embedding
    orig_embedding = data["sequence_embeddings"]

    # Apply transformation
    transformed_embedding = orig_embedding + cat_to_cat_cat

    # Decode both original and transformed
    orig_decoded = encoder_decoder.token_ids_to_list_str_batch(
        encoder_decoder.decode(orig_embedding.unsqueeze(0))
    )
    trans_decoded = encoder_decoder.token_ids_to_list_str_batch(
        encoder_decoder.decode(transformed_embedding.unsqueeze(0))
    )

    # Save results
    results.append(
        {"sequence": sequence, "original": orig_decoded, "transformed": trans_decoded}
    )

# Print all results
for result in results:
    print(f"\nOriginal token: {result['sequence']}")
    print(f"Original decoded: {result['original']}")
    print(f"Transformed decoded: {result['transformed']}")

# %%
sequence_length = 20
sequences = [
    tuple(["dog" if i == j else "a" for i in range(sequence_length)])
    for j in range(sequence_length)
]

# Get embeddings for each token
test_embeddings = {}
for sequence in sequences:
    sentence_embeddings, encoded_seqs = encoder_decoder.encode(
        torch.cat(
            [
                encoder_decoder.list_str_to_token_ids_batch([sequence]),
            ]
        )
    )
    test_embeddings[sequence] = {
        "sequence_embeddings": sentence_embeddings,
        "decoded": encoder_decoder.token_ids_to_list_str_batch(
            encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
        ),
    }
test_embeddings
# %%
# Convert embeddings to numpy arrays and stack them
embeddings_list = []
labels = []
for sequence, data in test_embeddings.items():
    embeddings_list.append(data["sequence_embeddings"].detach().cpu().numpy())
    labels.append(sequence)

all_embeddings = np.vstack(embeddings_list)

# Perform PCA
from sklearn.decomposition import PCA

pca = PCA(n_components=3)
embeddings_3d = pca.fit_transform(all_embeddings)

# Create interactive 3D plot
import plotly.express as px

# Create a DataFrame for plotting
plot_data = pd.DataFrame(embeddings_3d, columns=["PC1", "PC2", "PC3"])
plot_data["dog_position"] = [sequence.index("dog") for sequence in labels]

fig = px.scatter_3d(
    plot_data,
    x="PC1",
    y="PC2",
    z="PC3",
    color="dog_position",
    labels={
        "PC1": "First Principal Component",
        "PC2": "Second Principal Component",
        "PC3": "Third Principal Component",
        "dog_position": 'Position of "dog"',
    },
    title="3D PCA of Sequence Embeddings",
)
fig.show()


# %%
# Create sequences with "cat" at different positions
cat_sequences = [
    tuple(["cat" if i == j else "a" for i in range(sequence_length)])
    for j in range(sequence_length)
]

# Get embeddings for cat sequences
for sequence in cat_sequences:
    sentence_embeddings, encoded_seqs = encoder_decoder.encode(
        torch.cat(
            [
                encoder_decoder.list_str_to_token_ids_batch([sequence]),
            ]
        )
    )
    test_embeddings[sequence] = {
        "sequence_embeddings": sentence_embeddings,
        "decoded": encoder_decoder.token_ids_to_list_str_batch(
            encoder_decoder.decode(sentence_embeddings.unsqueeze(0))
        ),
    }

# Update embeddings list and labels with cat sequences
embeddings_list = []
labels = []
for sequence, data in test_embeddings.items():
    embeddings_list.append(data["sequence_embeddings"].detach().cpu().numpy())
    labels.append(sequence)

all_embeddings = np.vstack(embeddings_list)

# Rerun PCA with updated data
pca = PCA(n_components=3)
embeddings_3d = pca.fit_transform(all_embeddings)

# Create interactive 3D plot showing both dog and cat positions together
plot_data = pd.DataFrame(embeddings_3d, columns=["PC1", "PC2", "PC3"])

# Create separate dataframes for dog and cat positions
dog_data = plot_data.copy()
dog_data["position"] = [
    sequence.index("dog") if "dog" in sequence else -1 for sequence in labels
]
dog_mask = dog_data["position"] != -1

cat_data = plot_data.copy()
cat_data["position"] = [
    sequence.index("cat") if "cat" in sequence else -1 for sequence in labels
]
cat_mask = cat_data["position"] != -1

# Create single 3D scatter plot
fig = go.Figure()

# Add dog position markers (only where dog exists)
fig.add_trace(
    go.Scatter3d(
        x=dog_data[dog_mask]["PC1"],
        y=dog_data[dog_mask]["PC2"],
        z=dog_data[dog_mask]["PC3"],
        mode="markers",
        marker=dict(
            size=8,
            color=dog_data[dog_mask]["position"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(x=0.9, title="Dog Position"),
        ),
        name="Dog Position",
    )
)

# Add cat position markers (only where cat exists)
fig.add_trace(
    go.Scatter3d(
        x=cat_data[cat_mask]["PC1"],
        y=cat_data[cat_mask]["PC2"],
        z=cat_data[cat_mask]["PC3"],
        mode="markers",
        marker=dict(
            size=8,
            color=cat_data[cat_mask]["position"],
            colorscale="Plasma",
            showscale=True,
            colorbar=dict(x=1.0, title="Cat Position"),
        ),
        name="Cat Position",
    )
)

# Update layout
fig.update_layout(
    title="3D PCA of Sequence Embeddings - Dog and Cat Positions",
    scene=dict(
        xaxis_title="First Principal Component",
        yaxis_title="Second Principal Component",
        zaxis_title="Third Principal Component",
    ),
    width=1000,
    height=800,
)

fig.show()

# %%


position_3_to_4 = (
    test_embeddings[tuple(["a"] * 4 + ["dog"] + ["a"] * (sequence_length - 5))][
        "sequence_embeddings"
    ]
    - test_embeddings[tuple(["a"] * 3 + ["dog"] + ["a"] * (sequence_length - 4))][
        "sequence_embeddings"
    ]
)
# %%
cat_3_shifted_to_4 = (
    test_embeddings[tuple(["a"] * 3 + ["cat"] + ["a"] * (sequence_length - 4))][
        "sequence_embeddings"
    ]
    + position_3_to_4
)
# %%
# Decode the shifted embedding
decoded_cat_shifted = encoder_decoder.token_ids_to_list_str_batch(
    encoder_decoder.decode(cat_3_shifted_to_4.unsqueeze(0))
)
print("\nDecoded sequence after shifting 'cat' from position 4 to 5:")
print(decoded_cat_shifted)

# %%
# Create test embeddings for "run" at different positions
# Create test embeddings for "run" at different positions
# Create test embeddings for "run" at different positions
# Create test embeddings for "speak" at different positions

sequence_length = 20

filler_token = "cat"

for filler_token in [
    "one",
    "an",
    "the",
    "a",
    "cat",
    "dog",
    "speak",
    "_",
    "-",
    ".",
    ",",
]:
    print(f"{filler_token=}")
    # Create dog embeddings and PCA data
    test_embeddings_dog = {}
    dog_data = []
    for pos in range(sequence_length - 1):
        sequence = [filler_token] * sequence_length
        sequence[pos] = "dog"
        sequence_tensor = encoder_decoder.list_str_to_token_ids_batch([sequence])
        with torch.no_grad():
            sequence_embeddings = encoder_decoder.encode(sequence_tensor)
        test_embeddings_dog[tuple(sequence)] = {
            "sequence": sequence,
            "sequence_embeddings": sequence_embeddings[0],
        }
        embedding = sequence_embeddings[0]
        pca_coords = pca.transform(embedding.cpu().detach().numpy().reshape(1, -1))[0]
        dog_data.append(
            {
                "position": pos + 1,
                "x": pca_coords[0],
                "y": pca_coords[1],
                "z": pca_coords[2],
            }
        )

    dog_data = pd.DataFrame(dog_data)

    # Create cat embeddings and PCA data
    test_embeddings_cat = {}
    cat_data = []
    for pos in range(sequence_length - 1):
        sequence = [filler_token] * sequence_length
        sequence[pos] = "cat"
        sequence_tensor = encoder_decoder.list_str_to_token_ids_batch([sequence])
        with torch.no_grad():
            sequence_embeddings = encoder_decoder.encode(sequence_tensor)
        test_embeddings_cat[tuple(sequence)] = {
            "sequence": sequence,
            "sequence_embeddings": sequence_embeddings[0],
        }
        embedding = sequence_embeddings[0]
        pca_coords = pca.transform(embedding.cpu().detach().numpy().reshape(1, -1))[0]
        cat_data.append(
            {
                "position": pos + 1,
                "x": pca_coords[0],
                "y": pca_coords[1],
                "z": pca_coords[2],
            }
        )

    cat_data = pd.DataFrame(cat_data)

    # Create speak embeddings and PCA data
    test_embeddings = {}
    speak_data = []
    for pos in range(sequence_length - 1):
        sequence = [filler_token] * sequence_length
        sequence[pos] = "speak"
        sequence_tensor = encoder_decoder.list_str_to_token_ids_batch([sequence])
        with torch.no_grad():
            sequence_embeddings = encoder_decoder.encode(sequence_tensor)
        test_embeddings[tuple(sequence)] = {
            "sequence": sequence,
            "sequence_embeddings": sequence_embeddings[0],
        }
        embedding = sequence_embeddings[0]
        pca_coords = pca.transform(embedding.cpu().detach().numpy().reshape(1, -1))[0]
        speak_data.append(
            {
                "position": pos + 1,
                "x": pca_coords[0],
                "y": pca_coords[1],
                "z": pca_coords[2],
            }
        )

    speak_data = pd.DataFrame(speak_data)

    # Create the 3D scatter plot with all curves
    fig = go.Figure()

    # Add the dog positions
    fig.add_trace(
        go.Scatter3d(
            x=dog_data["x"],
            y=dog_data["y"],
            z=dog_data["z"],
            mode="markers+lines",
            marker=dict(
                size=5,
                color=dog_data["position"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Dog Position"),
            ),
            name="Dog Position",
        )
    )

    # Add the cat positions
    fig.add_trace(
        go.Scatter3d(
            x=cat_data["x"],
            y=cat_data["y"],
            z=cat_data["z"],
            mode="markers+lines",
            marker=dict(
                size=5,
                color=cat_data["position"],
                colorscale="Plasma",
                showscale=True,
                colorbar=dict(x=1.0, title="Cat Position"),
            ),
            name="Cat Position",
        )
    )

    # Add the speak positions
    fig.add_trace(
        go.Scatter3d(
            x=speak_data["x"],
            y=speak_data["y"],
            z=speak_data["z"],
            mode="markers+lines",
            marker=dict(
                size=5,
                color=speak_data["position"],
                colorscale="Turbo",
                showscale=True,
                colorbar=dict(x=1.1, title="Speak Position"),
            ),
            name="Speak Position",
        )
    )

    # Update layout
    fig.update_layout(
        title="3D PCA of Sequence Embeddings - Dog, Cat and Speak Positions",
        scene=dict(
            xaxis_title="First Principal Component",
            yaxis_title="Second Principal Component",
            zaxis_title="Third Principal Component",
        ),
        width=1000,
        height=800,
    )

    fig.show()

# %%
