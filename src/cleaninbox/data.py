from pathlib import Path
import json
from typing import Tuple, Optional

from datasets import load_dataset
from torch.utils.data import Dataset, TensorDataset
import datasets
from loguru import logger
from transformers import BertTokenizer
import torch
from hydra.utils import to_absolute_path #for resolving paths as originally for loading data
import hydra
from hydra import compose, initialize
from omegaconf import DictConfig, OmegaConf
from loguru import logger
import sys
from torch.utils.data import random_split
from google.cloud.storage import Bucket
import io
import pandas as pd
from google.cloud import storage

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{message}</green> | {level} | {time:HH:mm:ss}")

class MyDataset(Dataset):
    """My custom dataset."""

    def __init__(self, raw_data_path: Path, raw_dir: Path, proc_dir: Path) -> None:
        self.data_path = raw_data_path
        self.raw_dir = Path(to_absolute_path(raw_dir)) / Path(self.data_path).stem
        self.proc_dir = Path(to_absolute_path(proc_dir)) / Path(self.data_path).stem
        logger.info(f"Raw data path: {self.raw_dir}")

    def __len__(self): #Could also be empty
        return len(self.train_text) if hasattr(self, "train_text") else 0

    def __getitem__(self, index): #Could also be empty
        return {
            "input_ids": self.train_text[index],
            "labels": self.train_labels[index]
        }

    @logger.catch(level="ERROR")
    def download_data(self, dset_name: str) -> datasets.dataset_dict.DatasetDict:
        logger.info(f"Collecting and unpacking dataset {dset_name}.")
        dataset = load_dataset(dset_name,trust_remote_code=True)
        return dataset

    @logger.catch(level="ERROR")
    def preprocess(self, model_name: str) -> None:

        # Load data:
        dataset = self.download_data(self.data_path)
        train_text_l, train_labels_l = dataset["train"]["text"], dataset["train"]["label"]
        test_text_l, test_labels_l = dataset["test"]["text"], dataset["test"]["label"]

        #tokenize data:
        tokenizer = BertTokenizer.from_pretrained(model_name)
        train_text = tokenize_data(train_text_l,tokenizer) # N x maxSeqLen
        test_text = tokenize_data(test_text_l,tokenizer) # N x maxSeqLen

        train_labels = torch.tensor(train_labels_l).long()
        test_labels = torch.tensor(test_labels_l).long()

        # Save processed data:
        logger.info(f"Saving processed data to {self.proc_dir}.")
        self.proc_dir.mkdir(parents=True, exist_ok=True)
        torch.save(train_text, self.proc_dir / "train_text.pt")
        torch.save(train_labels, self.proc_dir / "train_labels.pt")
        torch.save(test_text, self.proc_dir / "test_text.pt")
        torch.save(test_labels, self.proc_dir / "test_labels.pt")

        #save a dictionary of label-to-string class mapping
        labelDict = {0: "activate_my_card",1: "age_limit",2: "apple_pay_or_google_pay",3: "atm_support",4: "automatic_top_up",5: "balance_not_updated_after_bank_transfer",6: "balance_not_updated_after_cheque_or_cash_deposit",7: "beneficiary_not_allowed",8: "cancel_transfer",9: "card_about_to_expire",10: "card_acceptance",11: "card_arrival",12: "card_delivery_estimate",13: "card_linking",14: "card_not_working",15: "card_payment_fee_charged",16: "card_payment_not_recognised",17: "card_payment_wrong_exchange_rate",18: "card_swallowed",19: "cash_withdrawal_charge",20: "cash_withdrawal_not_recognised",21: "change_pin",22: "compromised_card",23: "contactless_not_working",24: "country_support",25: "declined_card_payment",26: "declined_cash_withdrawal",27: "declined_transfer",28: "direct_debit_payment_not_recognised",29: "disposable_card_limits",30: "edit_personal_details",31: "exchange_charge",32: "exchange_rate",33: "exchange_via_app",34: "extra_charge_on_statement",35: "failed_transfer",36: "fiat_currency_support",37: "get_disposable_virtual_card",38: "get_physical_card",39: "getting_spare_card",40: "getting_virtual_card",41: "lost_or_stolen_card",42: "lost_or_stolen_phone",43: "order_physical_card",44: "passcode_forgotten",45: "pending_card_payment",46: "pending_cash_withdrawal",47: "pending_top_up",48: "pending_transfer",49: "pin_blocked",50: "receiving_money",51: "Refund_not_showing_up",52: "request_refund",53: "reverted_card_payment",54: "supported_cards_and_currencies",55: "terminate_account",56: "top_up_by_bank_transfer_charge",57: "top_up_by_card_charge",58: "top_up_by_cash_or_cheque",59: "top_up_failed",60: "top_up_limits",61: "top_up_reverted",62: "topping_up_by_card",63: "transaction_charged_twice",64: "transfer_fee_charged",65: "transfer_into_account",66: "transfer_not_received_by_recipient",67: "transfer_timing",68: "unable_to_verify_identity",69: "verify_my_identity",70: "verify_source_of_funds",71: "verify_top_up",72: "virtual_card_not_working",73: "visa_or_mastercard",74: "why_verify_identity",75: "wrong_amount_of_cash_received",
                    76: "wrong_exchange_rate_for_cash_withdrawal"}
        with open(self.proc_dir / "label_strings.json","w") as f:
            json.dump(labelDict,f)

        # Save raw data:
        logger.info(f"Saving raw data to {self.raw_dir}.")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        with open(self.raw_dir / "train_text.json", 'w') as f:
            json.dump(train_text_l,f)

        with open(self.raw_dir / "train_labels.json", 'w') as f:
            json.dump(train_labels_l,f)

        with open(self.raw_dir / "test_text.json", 'w') as f:
            json.dump(test_text_l,f)

        with open(self.raw_dir / "test_labels.json", 'w') as f:
            json.dump(test_labels_l,f)


def tokenize_data(self, text: list, tokenizer: BertTokenizer) -> torch.Tensor:
        """ Tokenize the input text data. """
        encoding = tokenizer(text,# List of input texts
        padding=True,              # Pad to the maximum sequence length
        truncation=False,           # Truncate to the maximum sequence length if necessary
        return_tensors='pt',      # Return PyTorch tensors
        add_special_tokens=True    # Add special tokens CLS and SEP <- possibly uneeded
        )
        return encoding

def load_label_strings(proc_path, dataset_name) -> dict[int,str]:
    """
    Loads the integer class-label corresponding string labels for visualizations during training
    Args:
        proc_path (_type_): Path object to the processed dir

    Returns:
        dict[int,str]: dictionary mapping from integer labels to string labels
    """
    logger.info(f"Loading string labels: {dataset_name}")
    proc_path = Path(to_absolute_path(proc_path)) / Path(dataset_name).stem
    with open(proc_path / "label_strings.json","r") as f:
        return json.load(f)

def get_data(bucket: Bucket, proc_path: Path):
    if bucket:
        # Load processed data from GCS:
        data_blobs = bucket.list_blobs(prefix=proc_path)
        logger.info(f"Loading processed data from GCS: {proc_path}")
        train_text, train_labels, test_text, test_labels = None, None, None, None
        for blob in data_blobs:
            logger.info(f"Downloading blob: {blob.name}")
            if blob.name.endswith(".pt"):
                data_bytes = blob.download_as_bytes()
                data = torch.load(io.BytesIO(data_bytes))
                if "train_text" in blob.name:
                    train_text = data
                elif "train_labels" in blob.name:
                    train_labels = data
                elif "test_text" in blob.name:
                    test_text = data
                elif "test_labels" in blob.name:
                    test_labels = data

        return train_text, train_labels, test_text, test_labels

    # Get locally processed data:
    train_text = torch.load(proc_path / "train_text.pt")
    train_labels = torch.load(proc_path / "train_labels.pt")
    test_text = torch.load(proc_path / "test_text.pt")
    test_labels = torch.load(proc_path / "test_labels.pt")

    return train_text, train_labels, test_text, test_labels

def get_monitoring_data(bucket: Bucket, monitor_path: Path):
    if bucket:
        # Load processed data from GCS:
        data_blobs = bucket.list_blobs(prefix=monitor_path)
        logger.info(f"Loading monitoring data from GCS: {monitor_path}")
        reference_data, new_data = None, None
        for blob in data_blobs:
            logger.info(f"Checking blob: {blob.name}")
            if blob.name.endswith(".csv"):
                logger.info(f"Downloading blob: {blob.name}")
                data_bytes = blob.download_as_bytes()
                new_data = pd.read_csv(io.BytesIO(data_bytes))

            elif blob.name.endswith(".pkl"):
                logger.info(f"Downloading blob: {blob.name}")
                data_bytes = blob.download_as_bytes()
                reference_data = pd.read_pickle(io.BytesIO(data_bytes))

        return reference_data, new_data

    # Get local monitoring data:
    reference_data = pd.read_pickle(monitor_path / "reference_data.pkl")
    new_data = pd.read_csv(monitor_path / "newdata_predictions_db.csv")

    return reference_data, new_data

def make_reference_data(bucket: Bucket, raw_path: Path = "./data/raw/banking77", monitor_path: Path = "./data/monitoring") -> None:
    if bucket:
        data_blobs = bucket.list_blobs(prefix=raw_path)
        logger.info(f"Loading processed data from GCS: {raw_path}")
        reference_data, reference_inputs, reference_targets = None, None, None
        for blob in data_blobs:
            logger.info(f"Checking blob: {blob.name}")
            if blob.name.endswith(".json"):
                if "train_text" in blob.name:
                    logger.info(f"Downloading blob: {blob.name}")
                    data_bytes = blob.download_as_bytes()
                    reference_inputs = json.load(io.BytesIO(data_bytes))
                elif "train_labels" in blob.name:
                    logger.info(f"Downloading blob: {blob.name}")
                    data_bytes = blob.download_as_bytes()
                    reference_targets = json.load(io.BytesIO(data_bytes))
        # {timestamp},{model_name},{len(prompt)},{prediction},{prediction_time}
        reference_data = pd.DataFrame({
            "input_length": [len(text) for text in reference_inputs],
            "target": reference_targets
        })

        # Save reference data to GCS:
        buffer = io.BytesIO()
        reference_data.to_pickle(buffer)
        buffer.seek(0)
        blob = bucket.blob(f"{monitor_path}/reference_data.pkl")
        blob.upload_from_file(buffer, content_type="application/octet-stream")

        return

    # Locally save reference data:
    reference_inputs = json.load(raw_path / "train_text.json")
    reference_targets = json.load(raw_path / "train_labels.json")
    reference_data = pd.DataFrame({
        "input_length": [len(text) for text in reference_inputs],
        "target": reference_targets
    })
    reference_data.to_pickle(monitor_path / "reference_data.pkl")
    return

def text_dataset(val_size, proc_path, dataset_name, seed, bucket: Bucket=None) -> Tuple[TensorDataset, TensorDataset, TensorDataset]:
    """ Load the processed text dataset. """

    logger.info(f"Loading processed data: {dataset_name}, proc_path: {proc_path}")
    proc_path = Path(to_absolute_path(proc_path)) / Path(dataset_name).stem if not bucket else proc_path
    logger.info(f"text_dataset has path: {proc_path}")

    train_text, train_labels, test_text, test_labels = get_data(bucket, proc_path)
    train = TensorDataset(train_text["input_ids"], train_text["token_type_ids"], train_text["attention_mask"],train_labels)
    test = TensorDataset(test_text["input_ids"], test_text["token_type_ids"], test_text["attention_mask"], test_labels)

    # Split training data into training and validation sets:
    if val_size > 0:
        val_size = int(len(train) * val_size)
        train_size = len(train) - val_size
        train, val = random_split(train, [train_size, val_size], generator=torch.Generator().manual_seed(seed))

        return train, val, test

    return train, None, test

@hydra.main(config_path="../../configs", config_name="config.yaml", version_base="1.1")
def preprocess(cfg: DictConfig) -> None:
    logger.info("Preprocessing data...")
    dataset = MyDataset(cfg.dataset.name, raw_dir=cfg.basic.raw_path, proc_dir=cfg.basic.proc_path)
    dataset.preprocess(model_name=cfg.model.name)

@hydra.main(config_path="../../configs", config_name="config.yaml", version_base="1.1")
def run_text_dataset(cfg: DictConfig) -> None:
    train, val, test = text_dataset(cfg.dataset.val_size, cfg.basic.proc_path, cfg.dataset.name, cfg.experiment.hyperparameters.seed)
    logger.info(f"Train size: {len(train)}, Val size: {len(val)}, Test size: {len(test)}")

# For making reference data for monitoring:
@hydra.main(config_path="../../configs", config_name="config.yaml", version_base="1.1")
def main(cfg: DictConfig) -> None:
    logger.info("Running main function...")

    storage_client = storage.Client()
    bucket = storage_client.bucket(cfg.gs.bucket)

    make_reference_data(bucket = bucket,
                        raw_path = Path(cfg.gs.raw_data),
                        monitor_path = Path(cfg.gs.monitoring))

if __name__ == "__main__":
    #preprocess()
    run_text_dataset()
    #main()
