"""Cancela uma intenção Demo pré-validada que não será enviada."""
import argparse
from demo_execution_gateway import default_journal_path
from execution_journal import load_journal, save_journal, transition

parser = argparse.ArgumentParser(); parser.add_argument('--intent', required=True)
args = parser.parse_args()
path = default_journal_path(); journal = load_journal(path)
item = next((x for x in journal['intents'] if x['id'] == args.intent), None)
if item and item['status'] in {'CREATED', 'PREFLIGHT_APPROVED'}:
    transition(item, 'CANCELLED', comment='Pré-validação cancelada pelo usuário.')
    save_journal(path, journal)
print('CANCELLED' if item else 'NOT_FOUND')
