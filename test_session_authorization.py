from session_authorization import SessionAuthorization


def test_session_authorization_is_session_scoped():
    session = SessionAuthorization()
    assert session.can_operate(0, 30)[0] is False
    session.authorize()
    assert session.can_operate(0, 30)[0] is True
    session.revoke()
    assert session.can_operate(0, 30)[0] is False


def test_daily_loss_requires_explicit_override():
    session = SessionAuthorization(); session.authorize()
    allowed, reason = session.can_operate(-30, 30)
    assert not allowed and 'limite' in reason
    session.confirm_loss_override()
    assert session.can_operate(-30, 30)[0] is True
