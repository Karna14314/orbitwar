from kaggle_environments import make
import importlib.util, os

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

def load_agent(path):
    spec = importlib.util.spec_from_file_location("agent_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent

def validate():
    champion = load_agent('agents/champion.py')
    challenger = load_agent('agents/experimental/agent_wave_current.py')

    env = make('orbit_wars', debug=False)
    env.run([champion, challenger])

    r0 = env.steps[-1][0].reward or 0
    r1 = env.steps[-1][1].reward or 0
    print(f"Validation Game Output: Champion={r0}, Wave={r1}")

if __name__ == '__main__':
    validate()
