"""Kernel installation script for Jupyter."""

import json
import os
import subprocess
import sys


def install_kernel(user=True):
    """Install the Kamailio CFG kernel for Jupyter."""
    from jupyter_client.kernelspec import KernelSpecManager

    ksm = KernelSpecManager()

    kernel_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "kernel_spec"
    )
    os.makedirs(kernel_dir, exist_ok=True)

    # Write kernel.json (VS Code Jupyter 호환)
    kernel_json = {
        "argv": [
            os.path.join(os.path.dirname(sys.executable), "python3"),
            "-m", "kamailio_notebook.kernel",
            "-f", "{connection_file}"
        ],
        "display_name": "Kamailio CFG",
        "language": "kamailio-cfg",
        "mimetype": "text/x-kamailio-cfg",
        "file_extension": ".cfg",
        "codemirror_mode": "shell",
        "interrupt_mode": "message",
    }

    kernel_json_path = os.path.join(kernel_dir, "kernel.json")
    with open(kernel_json_path, "w") as f:
        json.dump(kernel_json, f, indent=2)

    # Install
    ksm.install_kernel_spec(
        kernel_dir,
        kernel_name="kamailio-cfg",
        user=user,
        replace=True,
    )

    print("Kamailio CFG kernel installed successfully!")
    print("Run 'jupyter lab' and select 'Kamailio CFG' as your kernel.")


if __name__ == "__main__":
    install_kernel()
