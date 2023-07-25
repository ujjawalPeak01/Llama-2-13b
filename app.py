from threading import Thread
from typing import Iterator

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

model_id = 'meta-llama/Llama-2-13b-chat-hf'

class InferlessPythonModel:
    def get_prompt(self, message, chat_history,
               system_prompt):
        texts = [f'[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n']
        for user_input, response in chat_history:
            texts.append(f'{user_input.strip()} [/INST] {response.strip()} </s><s> [INST] ')
        texts.append(f'{message.strip()} [/INST]')
        return ''.join(texts)

    
    def get_input_token_length(self, message, chat_history, system_prompt):
        prompt = self.get_prompt(message, chat_history, system_prompt)
        input_ids = self.tokenizer([prompt], return_tensors='np')['input_ids']
        return input_ids.shape[-1]


    def run_function(self, message,
        chat_history,
        system_prompt,
        max_new_tokens=1024,
        temperature=0.8,
        top_p=0.95,
        top_k=5):
        prompt = self.get_prompt(message, chat_history, system_prompt)
        inputs = self.tokenizer([prompt], return_tensors='pt').to('cuda')

        streamer = TextIteratorStreamer(self.tokenizer,
                                        timeout=10.,
                                        skip_prompt=True,
                                        skip_special_tokens=True)
        generate_kwargs = dict(
            inputs,
            streamer=streamer,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            top_p=top_p,
            top_k=top_k,
            temperature=temperature,
            num_beams=1,
        )
        t = Thread(target=self.model.generate, kwargs=generate_kwargs)
        t.start()

        outputs = ''
        for text in streamer:
            outputs += text

        return outputs


    def initialize(self):
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_auth_token='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')


        if torch.cuda.is_available():
            config = AutoConfig.from_pretrained(model_id, use_auth_token='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')
            config.pretraining_tp = 1
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                config=config,
                torch_dtype=torch.float16,
                device_map='auto',
                load_in_4bit=True,
                use_auth_token='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'
            )
        else:
            self.model = None

    def infer(self, inputs):
        message = inputs['message']
        chat_history = inputs['chat_history'] if 'chat_history' in inputs else []
        system_prompt = inputs['system_prompt'] if 'system_prompt' in inputs else ''
        result = self.run_function(
            message=message,
            chat_history=chat_history,
            system_prompt=system_prompt,
        )
        return {"generated_text": result}

    def finalize(self):
        self.tokenizer = None
        self.model = None
