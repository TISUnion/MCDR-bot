from threading import RLock
from typing import List, Dict, Optional

from mcdreforged.api.all import *

from .minecraft.networking.connection import NetworkingThread, Connection


class Bot:
	def __init__(self, storage: 'BotStorage', name: str, address: str, port: int):
		self.__storage = storage
		self.name = name
		self.connection = Connection(
			address=address,
			port=port,
			auth_token=None,
			username=name,
			handle_exception=self.handle_exception,
			handle_exit=self.handle_exit
		)
		self.connection.connect()

	def stop(self):
		self.connection.disconnect()

	def handle_exception(self, exc, exc_info):
		ServerInterface.get_instance().logger.warning('Exception at MCDR bot {}: {}'.format(self.name, exc))
		self.handle_exit()

	def handle_exit(self):
		ServerInterface.get_instance().logger.warning('Disconnected')
		self.__storage.remove_bot(self.name)


class BotStorage(Dict[str, Bot]):
	def __init__(self):
		super().__init__()
		self.__lock = RLock()
		self.__patch_pycraft()

	@staticmethod
	def __patch_pycraft():
		def modify_thread_name(self, *args, **kwargs):
			original_init(self, *args, **kwargs)
			self.name = 'MCDR-Bot {}'.format(self.connection.username)
		original_init = NetworkingThread.__init__
		NetworkingThread.__init__ = modify_thread_name

	def add_bot(self, name: str, address: str, port: int) -> bool:
		bot = Bot(self, name, address, port)
		if bot.connection.connected:
			with self.__lock:
				self[name] = bot
		return bot.connection.connected

	def get_bot(self, name: str) -> Optional[Bot]:
		with self.__lock:
			return self.get(name)

	def is_bot(self, name: str) -> bool:
		return self.get_bot(name) is not None

	def remove_bot(self, name: str) -> bool:
		with self.__lock:
			bot = self.pop(name, None)
		if bot is not None:
			try:
				bot.stop()
			except:
				pass
			return True
		else:
			return False

	def get_bot_name_list(self) -> List[str]:
		with self.__lock:
			return list(self.keys())

	def import_bots(self, storage: dict):
		for name, bot in list(storage.items()):
			if isinstance(name, str) and getattr(type(bot), '__name__', None) == 'Bot':
				with self.__lock:
					ServerInterface.get_instance().logger.info('Imported bot {} from previous plugin instance'.format(name))
					self[name] = bot
