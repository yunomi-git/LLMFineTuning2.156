## Working example of fine tuning with PEFT

from peft import LoraConfig, prepare_model_for_kbit_training, get_peft_model
from trl import SFTTrainer
from datasets import load_dataset, concatenate_datasets
from transformers import DataCollatorForLanguageModeling
from transformers import AutoModelForCausalLM, TrainingArguments, Trainer
from transformers import AutoTokenizer, BitsAndBytesConfig

import torch
import paths

torch.cuda.empty_cache()


configuration = {
    "peft_mode": "Lora",
    "data_size": 0.0001,
    "block_size": 1024,
    "batch_size": 2,
    "gradient_accumulation_steps": 2
}
name = "yu-nomi/llama-wiki-standards"
revision = str(configuration["peft_mode"])  \
            + "_D" + str(configuration["data_size"])  \
            + "_Bl" + str(configuration["block_size"])
            # + "_Ba" + str(configuration["batch_size"])  \
            # + "_Ga" + str(configuration["gradient_accumulation_steps"])
print(name)
print(revision)
save_name = name+"_"+revision

peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.1,
        r=64,
        bias="none",
        task_type="CAUSAL_LM",
)


use_flash_attention = False
# BitsAndBytesConfig int-4 config
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16
)


print("model")
model = AutoModelForCausalLM.from_pretrained(paths.llama_checkpoint,
                                             trust_remote_code=True,
                                             token=paths.annie_read_token,
                                             device_map="auto",
                                             use_cache=False,
                                             quantization_config=bnb_config,
                                             use_flash_attention_2=use_flash_attention
                                             )
# model = AutoModelForCausalLM.from_pretrained(paths.llama_local_checkpoint,
#                                              device_map="auto",
#                                              use_cache=False,
#                                              quantization_config=bnb_config,
#                                              use_flash_attention_2=use_flash_attention)
model.config.pretraining_tp = 1
model = prepare_model_for_kbit_training(model)
# model.print_trainable_parameters()

print("tokenizer")
tokenizer = AutoTokenizer.from_pretrained(paths.llama_checkpoint,
                                          trust_remote_code=True,
                                          token=paths.annie_read_token,
                                          use_fast=True)
# tokenizer = AutoTokenizer.from_pretrained(paths.llama_local_checkpoint,
#                                           use_fast=True,
#                                           use_reentrant=False,
#                                           )
tokenizer.pad_token = tokenizer.eos_token #"<pad>"
tokenizer.padding_side = "right"

print("datasets")
max_size = 1000000
small_size = int(max_size * configuration["data_size"])
standards_dataset = load_dataset(paths.standards_dataset_checkpoint,
                                 split="train[:" + str(9*small_size) + "]",
                                 token=paths.nomi_read_token)
wiki_dataset = load_dataset(paths.wikipedia_dataset_checkpoint,
                            split="train[:" + str(small_size) + "]",
                            token=paths.nomi_read_token)
dataset = concatenate_datasets([standards_dataset, wiki_dataset])

dataset = dataset.train_test_split(test_size=0.2)
dataset = dataset.flatten()

block_size = configuration["block_size"]



num_proc = 128 # increasing increases overhead and decreases processing time. FInd equillibrium

# def preprocess_function(examples):
#     return tokenizer([" ".join(x) for x in examples["text"]])
#
# tokenized_dataset = dataset.map(
#     preprocess_function,
#     batched=True,
#     num_proc=num_proc,
#     remove_columns=dataset["train"].column_names,
# )
#
#
# def group_texts(examples):
#     # Concatenate all texts.
#     concatenated_examples = {k: sum(examples[k], []) for k in examples.keys()}
#     total_length = len(concatenated_examples[list(examples.keys())[0]])
#     # We drop the small remainder, we could add padding if the model supported it instead of this drop, you can
#     # customize this part to your needs.
#     if total_length >= block_size:
#         total_length = (total_length // block_size) * block_size
#     # Split by chunks of block_size.
#     result = {
#         k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
#         for k, t in concatenated_examples.items()
#     }
#     result["labels"] = result["input_ids"].copy()
#     return result
#
# lm_dataset = tokenized_dataset.map(group_texts, batched=True, num_proc=num_proc)
#
#
# data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

training_args = TrainingArguments(
    output_dir=save_name,
    num_train_epochs=3,
    # per_device_train_batch_size=6 if use_flash_attention else 4,
    # gradient_accumulation_steps=2,
    gradient_checkpointing=True,
    optim="paged_adamw_32bit",
    logging_steps=10,
    save_strategy="epoch",
    learning_rate=2e-4,
    bf16=True,
    tf32=True,
    max_grad_norm=0.3,
    warmup_ratio=0.03,
    lr_scheduler_type="constant",
    disable_tqdm=True, # disable tqdm since with packing values are in correct
    push_to_hub=True,
    hub_token=paths.nomi_write_token,
    per_device_train_batch_size=configuration["batch_size"],
    gradient_accumulation_steps=configuration["gradient_accumulation_steps"]
)

# trainer = Trainer(
#     model=model,
#     args=training_args,
#     train_dataset=lm_dataset["train"],
#     eval_dataset=lm_dataset["test"],
#     data_collator=data_collator,
# )

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset["train"],
    peft_config=peft_config,
    max_seq_length=block_size,
    tokenizer=tokenizer,
    packing=True,
    dataset_text_field="text",
    # formatting_func=format_instruction,
    args=training_args,
)

trainer.train()
trainer.save_model()
trainer.push_to_hub()
