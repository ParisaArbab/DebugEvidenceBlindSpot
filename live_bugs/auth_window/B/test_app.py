import app

def test_contract():
    assert app.run() == app.EXPECTED, 'contract validation failed'
