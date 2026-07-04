import torch, inspect
from transformers import AutoModelForCausalLM
m=AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-30B-A3B",dtype=torch.bfloat16,device_map={'':0}); m.eval()
blk=m.model.layers[0].mlp
print("MLP:",type(blk).__name__,"| gate:",type(blk.gate).__name__,"| experts:",type(blk.experts).__name__)
print("cfg: E",m.config.num_experts,"topk",m.config.num_experts_per_tok,"norm_topk",getattr(m.config,'norm_topk_prob',None))
print("===== SparseMoeBlock.forward =====")
print(inspect.getsource(type(blk).forward))
try:
    print("===== gate.forward =====")
    print(inspect.getsource(type(blk.gate).forward))
except Exception as e: print("gate src:",e)
try:
    print("===== experts.forward =====")
    print(inspect.getsource(type(blk.experts).forward)[:1500])
except Exception as e: print("experts src:",e)
