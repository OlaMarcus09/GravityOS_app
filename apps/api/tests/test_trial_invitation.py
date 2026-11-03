from app.integrations.trial_invitation import PLAN_BILLING_URL, SUBJECT, render_trial_invitation


def test_personalized_invitation_escapes_name_and_has_no_claim_link():
    email = render_trial_invitation(first_name='<Ada & Co>', unsubscribe_url='https://www.gravityos.tech/unsubscribe/test')
    assert email.subject == SUBJECT
    assert 'Hi &lt;Ada,' in email.html
    assert '<Ada' not in email.html
    assert PLAN_BILLING_URL in email.html and PLAN_BILLING_URL in email.text
    assert '/claim' not in email.html
    assert 'No payment card is required' in email.text
    assert 'There are no automatic charges' in email.text
    assert 'existing data remains available' in email.text
    assert 'Thank you for being one of the early GravityOS users' in email.text


def test_neutral_greeting_and_unsubscribe_url_required():
    email = render_trial_invitation(first_name=None, unsubscribe_url='https://example.com/unsubscribe')
    assert 'Hi there,' in email.html and 'Hi there,' in email.text


def test_rejects_non_https_unsubscribe_url():
    import pytest

    with pytest.raises(ValueError):
        render_trial_invitation(first_name='Ada', unsubscribe_url='http://example.com/unsubscribe')
