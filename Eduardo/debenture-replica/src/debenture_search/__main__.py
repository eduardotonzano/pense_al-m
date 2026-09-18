import argparse
from .aggregator import DebentureAggregator, NotFoundError
from .providers.snd import SndScraperProvider

def main():
    ap=argparse.ArgumentParser(description="Busca de debentures brasileiras")
    ap.add_argument("query")
    args=ap.parse_args()
    try: print(DebentureAggregator([SndScraperProvider()]).get(args.query))
    except NotFoundError: raise SystemExit("Ativo nao encontrado nos providers configurados")
if __name__ == "__main__": main()
