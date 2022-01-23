from collections import defaultdict
import re
from typing import List

import pandas as pd

import datasets
from datasets.dataset_dict import DatasetDict
from datasets import load_dataset
from transformers import AutoTokenizer, PreTrainedTokenizer

import torch
from torch.utils.data import Dataset

HuggingfaceDataset = DatasetDict
CHECKPOINT = 'microsoft/DialoGPT-large'
TOKENIZER = AutoTokenizer.from_pretrained(CHECKPOINT)


class DialoGPTDataset(Dataset):
    def __init__(
        self,
        data: HuggingfaceDataset,
        n_turns: int,
        tokenizer: PreTrainedTokenizer = AutoTokenizer.from_pretrained(
            CHECKPOINT)):

        super(DialoGPTDataset, self).__init__()
        self.dataset = data
        self.n_turns = n_turns
        self.tokenizer = tokenizer

        self.prepare_huggingface_dataset()

        #self.prepare_dataframe()
        #self.data = self.construct_data()

    @classmethod
    def empathetic_dialogues(cls, n_turns: int, preprocess: bool = True):
        """Reduces all dialogues into a common row

        Args:
            n_turns: how many turns of context to append

        Returns:
            Pytorch dataset class
        """
        # load dataset
        # reduce dialogues
        #
        if preprocess:
            pattern = re.compile(r'_conv:\d+')
            data = load_dataset('empathetic_dialogues')
            dataset = {}
            for k, split in data.items():
                convs = defaultdict(list)
                prompts = {}
                labels = {}

                for i, sample in enumerate(split):
                    conv_id = re.sub(pattern, '', sample['conv_id'])
                    convs[conv_id].append(sample['utterance'])
                    prompts[conv_id] = sample['prompt']
                    labels[conv_id] = sample['context']

                # insert situation into first position
                for i, j in prompts.items():
                    convs[i].insert(0, j)
                    convs[i] = f'{TOKENIZER.eos_token} '.join(convs[i])

                dataset[k] = datasets.Dataset.from_dict({
                    'dialog':
                    convs.values(),
                    'emotions':
                    labels.values()
                })

        return cls(data=DatasetDict(dataset),
                   n_turns=n_turns,
                   tokenizer=TOKENIZER)

    def prepare_dataframe(self):
        """Creates dataframe format necessary for DialoGPT as stated in paper"""
        columns = ['response', 'context']
        columns = columns + ['context/' + str(i) for i in range(self.n_turns)]
        dialogues = []
        for _, dataset in self.dataset.items():
            for sample in dataset:
                row = [
                    turn for i, turn in enumerate(sample)
                    if i < self.n_turns + 2
                ]
                dialogues.append(row)

        df = pd.DataFrame.from_records(dialogues, columns=columns)
        print(df.head())
        self.df = df

    def construct_data(self):
        def construct_conv(row: List[str]) -> List[int]:
            conv = [x + self.tokenizer.eos_token for x in row if x is not None]
            return ' '.join(conv)

        data = []
        for _, row in self.df.iterrows():
            conv = construct_conv(row)
            print(conv)
            data.append(conv)

        return data

    def prepare_huggingface_dataset(self):
        def tokenizing(sample):
            return self.tokenizer(sample['dialog'], truncation=True)

        def set_label(sample):
            sample['labels'] = sample['input_ids']
            return sample

        self.dataset = self.dataset.map(tokenizing, batched=True)
        self.dataset = self.dataset.map(set_label, batched=True)
        self.dataset = self.dataset.remove_columns(['emotions', 'dialog'])

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return torch.tensor(self.data[idx], dtype=torch.long)
