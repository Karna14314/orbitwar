import numpy as np

class Tournament:
    def __init__(self):
        self.results = []
        self.scores = {}

    def add_result(self, p1_name, p2_name, p1_score, p2_score):
        self.results.append({
            'p1': p1_name, 'p2': p2_name,
            's1': p1_score, 's2': p2_score
        })
        
        for name, score in [(p1_name, p1_score), (p2_name, p2_score)]:
            if name not in self.scores:
                self.scores[name] = []
            self.scores[name].append(score)

    def print_summary(self):
        print("Tournament Summary:")
        for name, scores in self.scores.items():
            avg = np.mean(scores)
            win_rate = sum(1 for s in scores if s > 50) / len(scores) # dummy win rate logic
            print(f"  {name:15}: avg_score={avg:6.2f}, win_rate={win_rate*100:4.1f}%")

class MetricsTracker:
    def __init__(self):
        self.metrics = {}

    def log(self, **kwargs):
        for k, v in kwargs.items():
            if k not in self.metrics:
                self.metrics[k] = []
            self.metrics[k].append(v)

    def summary(self):
        result = {}
        for k, v in self.metrics.items():
            result[k] = {
                'mean': np.mean(v),
                'last': v[-1] if v else 0,
                'max': np.max(v) if v else 0
            }
        return result
