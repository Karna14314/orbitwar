import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import random

class ImitationLearningBuffer:
    def __init__(self, capacity=10000):
        self.buffer = deque(maxlen=capacity)

    def add(self, global_feat, cand_feats, target_idx):
        self.buffer.append((global_feat, cand_feats, target_idx))

    def __len__(self):
        return len(self.buffer)

    def sample(self, batch_size):
        return random.sample(self.buffer, batch_size)

class ImitationLearningTrainer:
    def __init__(self, model, device='cpu', learning_rate=1e-3):
        self.model = model
        self.device = device
        self.optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        self.criterion = nn.CrossEntropyLoss()

    def train_step(self, batch):
        self.model.train()
        total_loss = 0
        
        for global_feat, cand_feats, target_idx in batch:
            g_torch = torch.from_numpy(global_feat).unsqueeze(0).to(self.device)
            c_torch = torch.from_numpy(cand_feats).unsqueeze(0).to(self.device)
            target = torch.tensor([target_idx], dtype=torch.long, device=self.device)
            
            self.optimizer.zero_grad()
            logits = self.model(g_torch, c_torch)
            loss = self.criterion(logits, target)
            loss.backward()
            self.optimizer.step()
            total_loss += loss.item()
            
        return total_loss / len(batch)

class RolloutBuffer:
    def __init__(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []

    def clear(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []

class PolicyGradientTrainer:
    def __init__(self, model, device='cpu', learning_rate=1e-4, entropy_coef=0.01):
        self.model = model
        self.device = device
        self.optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        self.entropy_coef = entropy_coef

    def train_step(self, logits, action, advantage):
        probs = torch.softmax(logits, dim=-1)
        log_probs = torch.log_softmax(logits, dim=-1)
        
        entropy = -(probs * log_probs).sum(-1).mean()
        action_log_prob = log_probs[action]
        
        loss = -(action_log_prob * advantage) - self.entropy_coef * entropy
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        return loss.item(), entropy.item()
