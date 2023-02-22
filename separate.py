# Para modelos que se van a ocupar
import torch
from asteroid import ConvTasNet
from asteroid.models import BaseModel

# Para grabar y reproducir audio
import soundfile as sf
from IPython.display import Audio

# Para trabajar con jack-audio
import jack

import sys
import signal
import os
import threading #Para usar hilos
import time
import queue # buena opción para trabajar con hilos 

import argparse


import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd


#--------------------------------------------MODELOS----------------------------------------------------------

# Modelo pre-entrenado DCCRNet
modelP = BaseModel.from_pretrained("JorisCos/DCCRNet_Libri1Mix_enhsingle_16k")

#Cargamos el modelo ConvTasNet
model1 = torch.load("/home/felix/model3_ConvTasNet.pth")

#Cargamos el modelo LSRMTasNet
model2 = torch.load("/home/felix/model1_LSTMTasNet.pth") 

#Cargamos el modelo SUDO
model3 = torch.load("/home/felix/sudo.pth")

#Cargamos el modelo DPTNET
model4 = torch.load("/home/felix/DPTNET.pth")

#Cargamos el modelo DCCRNet
model5 = torch.load("/home/felix/DCCRNet2.pth")


#------------------------------ INFERENCIA EN LINEA---------------------------------------

import threading
import queue

buffersize = 12
event = threading.Event()
clientname = "test"

def print_error(*args):
    print(*args, file=sys.stderr)

def xrun(delay):
    print_error("An xrun occured, increase JACK's period size?")

def shutdown(status, reason):
    print_error('JACK shutdown!')
    print_error('status:', status)
    print_error('reason:', reason)
    event.set()

def stop_callback(msg=''):
    if msg:
        print_error(msg)
    event.set()
    raise jack.CallbackExit


# Función que se ejecuta en el hilo separado
def separate_thread():
    while True:
        # Esperar a que haya suficientes datos en la cola circular
        #print(block_queue.qsize())
        while block_queue.qsize() < 13:
            time.sleep(0.01)

        # Obtener los datos de la cola circular y separar el audio
        mixture = block_queue.get()
        out_wavs = modelP.separate(mixture, resample=True)

        # Almacenar los datos de audio separados en la cola de salida
        output_queue.put(out_wavs)

# Función que se ejecuta en el hilo principal
def process(frames):
    if frames != blocksize:
        stop_callback('blocksize must not be changed, I quit!')

    # Leer los datos de audio y almacenarlos en la cola circular
    mixture = client.inports[0].get_array()[:]
    mixture = mixture.reshape(1, 1, mixture.shape[0])
    block_queue.put(mixture)

    # Obtener los datos de audio separados de la cola de salida y enviarlos al JACK
    if output_queue.qsize() > 0:
        out_wavs = output_queue.get()
        client.outports[0].get_buffer()[:] = out_wavs[0][0][:]

# Crear las colas y los hilos
block_queue = queue.Queue(maxsize=buffersize)
output_queue = queue.Queue()
separate_t = threading.Thread(target=separate_thread, daemon=True)

# Configurar el cliente JACK y los puertos
client = jack.Client(clientname, no_start_server=True)
blocksize = client.blocksize
samplerate = client.samplerate
client.set_xrun_callback(xrun)
client.set_shutdown_callback(shutdown)
client.set_process_callback(process)
client.inports.register('in_1')
client.outports.register('out_1')

# Conectar los puertos
with client:
    capture = client.get_ports(is_physical=True, is_output=True)
    if not capture:
        raise RuntimeError('No physical capture ports')
    for src, dest in zip(capture, client.inports):
        client.connect(src, dest)

    playback = client.get_ports(is_physical=True, is_input=True)
    if not playback:
        raise RuntimeError('No physical playback ports')
    for src, dest in zip(client.outports, playback):
        client.connect(src, dest)

    # Iniciar el hilo separado
    separate_t.start()

    # Esperar hasta que el usuario detenga la ejecución
    print('Press Ctrl+C to stop')
    try:
        event.wait()
    except KeyboardInterrupt:
        print('\nInterrupted by user')
        
        
        
