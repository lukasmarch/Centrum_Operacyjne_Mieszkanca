from regon_client import RegonClient

API_KEY = "b220c4e85a1b4e1da8b8"

def test_login():
    print("Testing connection to REGON API (PRODUKCJA)...")
    client = RegonClient(api_key=API_KEY, env='PRODUKCJA')
    
    success, sid = client.login()
    if success:
        print(f"Login SUCCESS! SID: {sid}")
        client.logout()
    else:
        print(f"Login FAILED. Error: {sid}")
        print("Trying TEST environment...")
        
        # Test env usually requires a specific test key, but let's try anyway just in case the key is for test
        client_test = RegonClient(api_key=API_KEY, env='TEST')
        success_test, sid_test = client_test.login()
        if success_test:
            print(f"Login SUCCESS on TEST env! SID: {sid_test}")
            client_test.logout()
        else:
            print(f"Login FAILED on TEST env too. Error: {sid_test}")

if __name__ == "__main__":
    test_login()
