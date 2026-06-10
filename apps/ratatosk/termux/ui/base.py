"""Abstract UI interface — terminal and Termux:GUI implement this."""

from abc import ABC, abstractmethod


class BaseUI(ABC):
    @abstractmethod
    def start(self):
        """Initialize the UI."""

    @abstractmethod
    def prompt(self) -> str:
        """Block until user submits input."""

    @abstractmethod
    def display(self, text: str, role: str = "assistant"):
        """Display a message."""

    @abstractmethod
    def stream_start(self):
        """Signal streaming output is about to begin."""

    @abstractmethod
    def stream_token(self, token: str):
        """Receive a streamed token."""

    @abstractmethod
    def stream_end(self):
        """Signal streaming complete."""

    @abstractmethod
    def status(self, text: str):
        """Show transient status."""

    @abstractmethod
    def stop(self):
        """Tear down UI."""
