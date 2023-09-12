import gradio

from facefusion.uis.components import about, processors, execution, source, webcam


def pre_check() -> bool:
	return True


def pre_render() -> bool:
	return True


def render() -> gradio.Blocks:
	with gradio.Blocks() as layout:
		with gradio.Row():
			with gradio.Column(scale = 2):
				with gradio.Box():
					about.render()
				with gradio.Blocks():
					processors.render()
				with gradio.Blocks():
					execution.render()
				with gradio.Blocks():
					source.render()
			with gradio.Column(scale = 5):
				with gradio.Blocks():
					webcam.render()
	return layout


def listen() -> None:
	processors.listen()
	execution.listen()
	source.listen()
	webcam.listen()


def run(ui : gradio.Blocks) -> None:
	ui.queue(concurrency_count = 2, api_open = False)
	ui.launch(show_api = False)
