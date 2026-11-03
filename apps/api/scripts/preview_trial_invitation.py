"""Write a synthetic invitation preview locally. This script never sends email."""

import argparse
from pathlib import Path

from app.integrations.trial_invitation import render_trial_invitation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first-name', default='Alex')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    email = render_trial_invitation(
        first_name=args.first_name,
        unsubscribe_url='https://example.com/preview-unsubscribe',
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(email.html, encoding='utf-8')
    args.output.with_suffix('.txt').write_text(email.text, encoding='utf-8')
    print(f'Synthetic preview written to {args.output}; no email sent.')


if __name__ == '__main__':
    main()
