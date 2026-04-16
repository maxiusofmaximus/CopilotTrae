def test_package_exposes_version():
    import local_ai_agent

    assert hasattr(local_ai_agent, "__version__")
