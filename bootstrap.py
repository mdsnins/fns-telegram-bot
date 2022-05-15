import service
import time
import config
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Wrong bootstrap")
    
    service.init()
    print(sys.argv)
    if sys.argv[1] == "load_prev":
        service.load_prev()

    if sys.argv[1] == "run_bot":
        while True:
            service.update()
            time.sleep(config.FNS_REFRESH_DURATION)
