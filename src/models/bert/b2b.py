# -*- coding: utf-8 -*-
"""Copy of BERT2BERT for CNN/Dailymail

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/11HF3kbPx1A89h27BI5rWBKm2GYYFD5Ew

## **Warm-starting BERT2BERT for CNN/Dailymail**

***Note***: This notebook only uses a few training, validation, and test data samples for demonstration purposes. To fine-tune an encoder-decoder model on the full training data, the user should change the training and data preprocessing parameters accordingly as highlighted by the comments.

### **Data Preprocessing**
"""

# Commented out IPython magic to ensure Python compatibility.
# %%capture
# !pip install datasets==1.0.2
# !pip install transformers
# 
import datasets
import transformers

from transformers import BertTokenizerFast

tokenizer = BertTokenizerFast.from_pretrained("bert-base-uncased")
tokenizer.bos_token = tokenizer.cls_token
tokenizer.eos_token = tokenizer.sep_token

train_data = datasets.load_dataset('benjaminbeilharz/ed-for-lm', split="train")
val_data = datasets.load_dataset("benjaminbeilharz/ed-for-lm", split="validation[:10%]")

batch_size=16
encoder_max_length=512
decoder_max_length=128

def process_data_to_model_inputs(batch):
    # tokenize the inputs and labels
    inputs = tokenizer(batch["history"], padding="max_length", truncation=True, max_length=encoder_max_length)
    outputs = tokenizer(batch["current"], padding="max_length", truncation=True, max_length=decoder_max_length)
    
    batch["input_ids"] = inputs.input_ids
    batch["attention_mask"] = inputs.attention_mask
    batch["decoder_input_ids"] = outputs.input_ids
    batch["decoder_attention_mask"] = outputs.attention_mask
    batch["labels"] = outputs.input_ids.copy()
    
    # because BERT automatically shifts the labels, the labels correspond exactly to `decoder_input_ids`. 
    # We have to make sure that the PAD token is ignored
    batch["labels"] = [[-100 if token == tokenizer.pad_token_id else token for token in labels] for labels in batch["labels"]]
    
    return batch

# only use 32 training examples for notebook - DELETE LINE FOR FULL TRAINING
# train_data = train_data.select(range(32))

train_data = train_data.map(
    process_data_to_model_inputs, 
    batched=True, 
    batch_size=batch_size, 
    remove_columns=["history", "current"]
)
train_data.set_format(
    type="torch", columns=["input_ids", "attention_mask", "decoder_input_ids", "decoder_attention_mask", "labels"],
)


# only use 16 training examples for notebook - DELETE LINE FOR FULL TRAINING
# val_data = val_data.select(range(16))

val_data = val_data.map(
    process_data_to_model_inputs, 
    batched=True, 
    batch_size=batch_size, 
    remove_columns=["history", "current"]
)
val_data.set_format(
    type="torch", columns=["input_ids", "attention_mask", "decoder_input_ids", "decoder_attention_mask", "labels"],
)

"""### **Warm-starting the Encoder-Decoder Model**"""

from transformers import EncoderDecoderModel, Seq2SeqTrainer

#bert2bert = EncoderDecoderModel.from_encoder_decoder_pretrained("bert-base-uncased", "bert-base-uncased")
#
## set special tokens
bert2bert.config.decoder_start_token_id = tokenizer.bos_token_id
bert2bert.config.eos_token_id = tokenizer.eos_token_id
bert2bert.config.pad_token_id = tokenizer.pad_token_id

# sensible parameters for beam search
bert2bert.config.vocab_size = bert2bert.config.decoder.vocab_size
bert2bert.config.max_length = 142
bert2bert.config.min_length = 56
bert2bert.config.no_repeat_ngram_size = 2
bert2bert.config.early_stopping = True
bert2bert.config.length_penalty = 2.0
bert2bert.config.num_beams = 4

"""### **Fine-Tuning Warm-Started Encoder-Decoder Models**

The `Seq2SeqTrainer` that can be found under [examples/seq2seq/seq2seq_trainer.py](https://github.com/huggingface/transformers/blob/master/examples/seq2seq/seq2seq_trainer.py) will be used to fine-tune a warm-started encoder-decoder model.

Let's download the `Seq2SeqTrainer` code and import the module along with `TrainingArguments`.
"""

# %%capture
# !rm seq2seq_trainer.py
# !wget https://raw.githubusercontent.com/huggingface/transformers/master/examples/seq2seq/seq2seq_trainer.py

from transformers import TrainingArguments
from dataclasses import dataclass, field
from typing import Optional

"""We need to add some additional parameters to make `TrainingArguments` compatible with the `Seq2SeqTrainer`. Let's just copy the `dataclass` arguments as defined in [this file](https://github.com/patrickvonplaten/transformers/blob/make_seq2seq_trainer_self_contained/examples/seq2seq/finetune_trainer.py)."""

@dataclass
class Seq2SeqTrainingArguments(TrainingArguments):
    label_smoothing: Optional[float] = field(
        default=0.0, metadata={"help": "The label smoothing epsilon to apply (if not zero)."}
    )
    sortish_sampler: bool = field(default=False, metadata={"help": "Whether to SortishSamler or not."})
    predict_with_generate: bool = field(
        default=False, metadata={"help": "Whether to use generate to calculate generative metrics (ROUGE, BLEU)."}
    )
    adafactor: bool = field(default=False, metadata={"help": "whether to use adafactor"})
    encoder_layerdrop: Optional[float] = field(
        default=None, metadata={"help": "Encoder layer dropout probability. Goes into model.config."}
    )
    decoder_layerdrop: Optional[float] = field(
        default=None, metadata={"help": "Decoder layer dropout probability. Goes into model.config."}
    )
    dropout: Optional[float] = field(default=None, metadata={"help": "Dropout probability. Goes into model.config."})
    attention_dropout: Optional[float] = field(
        default=None, metadata={"help": "Attention dropout probability. Goes into model.config."}
    )
    lr_scheduler: Optional[str] = field(
        default="linear", metadata={"help": f"Which lr scheduler to use."}
    )

"""Also, we need to define a function to correctly compute the ROUGE score during validation. ROUGE is a much better metric to track during training than only language modeling loss."""

# load rouge for validation
metric = datasets.load_metric("meteor")

def compute_metrics(pred):
    labels_ids = pred.label_ids
    pred_ids = pred.predictions

    # all unnecessary tokens are removed
    pred_str = tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
    labels_ids[labels_ids == -100] = tokenizer.pad_token_id
    label_str = tokenizer.batch_decode(labels_ids, skip_special_tokens=True)

    metrics = metric.compute(predictions=pred_str, references=label_str)

    return metrics

"""Cool! Finally, we start training."""

# set training arguments - these params are not really tuned, feel free to change
training_args = Seq2SeqTrainingArguments(
    output_dir="/",
    per_device_train_batch_size=batch_size,
    per_device_eval_batch_size=batch_size,
    predict_with_generate=True,
    # evaluate_during_training=True,
    do_train=True,
    do_eval=True,
    # logging_steps=2,  # set to 1000 for full training
    # save_steps=16,  # set to 500 for full training
    # eval_steps=4,  # set to 8000 for full training
    # warmup_steps=1,  # set to 2000 for full training
    # max_steps=16, # delete for full training
    overwrite_output_dir=True,
    save_total_limit=3,
    fp16=True, 
)

# instantiate trainer
#trainer = Seq2SeqTrainer(
#    model=bert2bert,
#    args=training_args,
#    compute_metrics=compute_metrics,
#    train_dataset=train_data,
#    eval_dataset=val_data,
#)
#trainer.train()

"""### **Evaluation**

Awesome, we finished training our dummy model. Let's now evaluated the model on the test data. We make use of the dataset's handy `.map()` function to generate a summary of each sample of the test data.
"""

import datasets
from transformers import BertTokenizer, EncoderDecoderModel

tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
model = EncoderDecoderModel.from_pretrained("./checkpoint-11000")
model.to("cuda")

test_data = datasets.load_dataset("benjaminbeilharz/ed-for-lm", split="test")


batch_size = 16  # change to 64 for full evaluation

# map data correctly
def generate_summary(batch):
    # Tokenizer will automatically set [BOS] <text> [EOS]
    # cut off at BERT max length 512
    inputs = tokenizer(batch["history"], padding="max_length", truncation=True, max_length=512, return_tensors="pt")
    input_ids = inputs.input_ids.to("cuda")
    attention_mask = inputs.attention_mask.to("cuda")

    outputs = model.generate(input_ids, attention_mask=attention_mask)

    # all special tokens including will be removed
    output_str = tokenizer.batch_decode(outputs, skip_special_tokens=True)

    batch["pred"] = output_str

    return batch

results = test_data.map(generate_summary, batched=True, batch_size=batch_size, remove_columns=["history"])

pred_str = results["pred"]
label_str = results["current"]

metrics = metric.compute(predictions=pred_str, references=label_str)

print(metrics)

"""The fully trained *BERT2BERT* model is uploaded to the 🤗model hub under [patrickvonplaten/bert2bert_cnn_daily_mail](https://huggingface.co/patrickvonplaten/bert2bert_cnn_daily_mail). 

The model achieves a ROUGE-2 score of **18.22**, which is even a little better than reported in the paper.

For some summarization examples, the reader is advised to use the online inference API of the model, [here](https://huggingface.co/patrickvonplaten/bert2bert_cnn_daily_mail).
"""
