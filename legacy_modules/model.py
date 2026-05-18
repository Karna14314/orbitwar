import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Optional

class CandidateRankerMLP(nn.Module):
    def __init__(self, global_state_dim: int, candidate_feature_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.cand_encoder = nn.Sequential(
            nn.Linear(candidate_feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )
        self.global_encoder = nn.Sequential(
            nn.Linear(global_state_dim, hidden_dim),
            nn.ReLU()
        )
        self.output_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, global_state: torch.Tensor, candidates: torch.Tensor) -> torch.Tensor:
        if global_state.dim() == 1:
            global_state = global_state.unsqueeze(0)
        if candidates.dim() == 2:
            candidates = candidates.unsqueeze(0)
            
        batch_size = global_state.size(0)
        num_cands = candidates.size(1)
        
        cand_embeds = self.cand_encoder(candidates)
        global_embeds = self.global_encoder(global_state).unsqueeze(1).expand(-1, num_cands, -1)
        
        combined = torch.cat([cand_embeds, global_embeds], dim=-1)
        logits = self.output_head(combined).squeeze(-1)
        
        if batch_size == 1:
            logits = logits.squeeze(0)
            
        return logits

def create_model(global_state_dim, candidate_feature_dim, hidden_dim=64, device='cpu'):
    model = CandidateRankerMLP(global_state_dim, candidate_feature_dim, hidden_dim)
    return model.to(device)

class NumpyInference:
    def __init__(self, weights: Dict[str, np.ndarray]):
        self.weights = weights

    @staticmethod
    def from_torch_model(model: nn.Module):
        weights = {k: v.cpu().numpy() for k, v in model.state_dict().items()}
        return NumpyInference(weights)

    def relu(self, x):
        return np.maximum(0, x)

    def linear(self, x, weight, bias):
        return x @ weight.T + bias

    def forward(self, global_state: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        if candidates.ndim == 1:
            candidates = candidates.reshape(1, -1)
            
        num_cands = candidates.shape[0]
        
        x_c = self.linear(candidates, self.weights['cand_encoder.0.weight'], self.weights['cand_encoder.0.bias'])
        x_c = self.relu(x_c)
        x_c = self.linear(x_c, self.weights['cand_encoder.2.weight'], self.weights['cand_encoder.2.bias'])
        x_c = self.relu(x_c)
        
        x_g = self.linear(global_state, self.weights['global_encoder.0.weight'], self.weights['global_encoder.0.bias'])
        x_g = self.relu(x_g)
        x_g = np.tile(x_g, (num_cands, 1))
        
        combined = np.concatenate([x_c, x_g], axis=-1)
        
        x = self.linear(combined, self.weights['output_head.0.weight'], self.weights['output_head.0.bias'])
        x = self.relu(x)
        logits = self.linear(x, self.weights['output_head.2.weight'], self.weights['output_head.2.bias'])
        
        return logits.flatten()

def export_model_weights(model, path):
    weights = {k: v.cpu().numpy() for k, v in model.state_dict().items()}
    np.savez(path, **weights)
