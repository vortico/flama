import subprocess


def build():
    print("🔥 Install js requirements...")
    subprocess.run(["npm", "install"], cwd="templates")
    print("🔥 Build templates...")
    subprocess.run(["npm", "run", "build"], cwd="templates")


if __name__ == "__main__":
    build()
