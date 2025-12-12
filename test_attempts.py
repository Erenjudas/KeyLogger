import sys, os
# Ensure backend package path is importable
sys.path.insert(0, os.path.dirname(__file__))

from api import record_failure, is_locked, record_success, LOGIN_ATTEMPTS


def simulate(username, tries):
    print(f"Simulating {tries} wrong attempts for user '{username}'")
    # clear any previous state
    if username in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[username]

    for i in range(tries):
        status, lock_seconds, attempts_left = record_failure(username)
        print(f"Attempt {i+1}: status={status}, lock_seconds={lock_seconds}, attempts_left={attempts_left}")
        locked, time_left = is_locked(username)
        print(f"  is_locked -> {locked}, time_left={time_left}")


if __name__ == '__main__':
    simulate('testuser', 6)
