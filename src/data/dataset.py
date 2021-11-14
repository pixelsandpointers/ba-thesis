"""
Declares abstract dataset class and implements datasets used in the project
"""
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import List, Union

import datasets
import numpy as np
import jax.numpy as jnp
import torch

from datasets import load_dataset

TorchType = torch.dtype
NumpyType = np.dtype
JaxType = jnp.dtype
Datatypes = Union[TorchType, NumpyType, JaxType]


HF_DS = ['empathetic-dialogues', 'daily-dialogue']


class Data(namedtuple):
    train: Union[TorchType, NumpyType, JaxType]
    valid: Union[TorchType, NumpyType, JaxType]
    test: Union[TorchType, NumpyType, JaxType]


class Dataset(ABC):
    @property
    @abstractmethod
    def headers(self) -> List[str]:
        pass

    @property
    @abstractmethod
    def train(self):
        return self._train

    @property
    @abstractmethod
    def valid(self):
        return self._valid

    @property
    @abstractmethod
    def test(self):
        return self._test

    @classmethod
    @abstractmethod
    def load(self, name: Union[None, str]):
        pass

    # @abstractmethod
    # def save(self):
    #     pass

    @abstractmethod
    def preprocess(self):
        pass

    @abstractmethod
    def prepare_tensors(self, tensor_type: str, dtype: Datatypes) -> Data:
        if tensor_type == 'torch':
            return (torch.tensor(self.train, dtype), torch.tensor(self.valid, dtype), torch.tensor(self.test, dtype))
        elif tensor_type == 'numpy':
            return (np.array(self.train, dtype), np.array(self.valid, dtype), np.array(self.test, dtype))
        elif tensor_type == 'jax':
            return (np.array(self.train, dtype), np.array(self.valid, dtype), np.array(self.test, dtype))
        else:
            raise ValueError(f'{dtype} is not supported.')


class HuggingfaceDataset(Dataset):
    def __init__(self, data: datasets.Dataset):
        self.data = data
        self._train, self._valid, self._test = [self.data[dataset] for dataset in self.data.keys()]

    @classmethod
    def load(cls, name: str):
        return cls(data=load_dataset(name))

    @train.setter
    def train(self, value):
        self._train = value

    @valid.setter
    def valid(self, value):
        self._valid = value

    @test.setter
    def test(self, value):
        self._test = value

    @property
    def headers(self) -> List[str]:
        return self._train[0].keys()


for n, d in zip([ed, dd], HF_DS):
    n = HuggingfaceDataset.load(name=d)