from socket import *
from struct import pack
from threading import Thread
import time
import json
import random

# Handshake data
HandShakeData1 = 'XtraLib.Stream.0\n'
HandShakeData2 = 'Tacview.RealTimeTelemetry.0\n'
HandShakeData3 = 'alpha_dog_fight\n'

# Data format
TelFileHeader = "FileType=text/acmi/tacview\nFileVersion=2.2\n"
TelReferenceTimeFormat = '0,ReferenceTime=%Y-%m-%dT%H:%M:%SZ\n'
TelDataFormat = '#%.2f\n3000102,T=%.7f|%.7f|%.7f|%.1f|%.1f|%.1f,AGL=%.3f,TAS=%.3f,CAS=%.3f,Type=Air+FixedWing,Name=Airbus A320,Color=Red,Coalition=Allies\n'

# TCP/IP parameters
LOCALPORT = 58008
LOCALIP = '127.0.0.1'


def generate_real_time_data():
    """
    Simulate generation of real-time flight data.
    """
    while True:
        # Simulate random flight parameters
        time_stamp = time.time()
        longitude = random.uniform(-180, 180)
        latitude = random.uniform(-90, 90)
        altitude = random.uniform(0, 10000)  # Altitude in meters
        roll = random.uniform(-180, 180)
        pitch = random.uniform(-90, 90)
        yaw = random.uniform(-180, 180)
        agl = altitude - 10  # Above ground level
        tas = random.uniform(200, 400)  # True airspeed
        cas = random.uniform(180, 380)  # Calibrated airspeed

        yield (time_stamp, longitude, latitude, altitude, roll, pitch, yaw, agl, tas, cas)


def serverthread(ss):
    flight_data_generator = generate_real_time_data()
    for flight_data in flight_data_generator:
        time.sleep(0.5)  # Simulate a delay
        data = TelDataFormat % (
            flight_data[0],  # Timestamp
            flight_data[1],  # Longitude
            flight_data[2],  # Latitude
            flight_data[3],  # Altitude
            flight_data[4],  # Roll
            flight_data[5],  # Pitch
            flight_data[6],  # Yaw
            flight_data[7],  # AGL
            flight_data[8],  # TAS
            flight_data[9]  # CAS
        )
        ss.send(data.encode('utf-8'))


def recv_msg():
    print("recv uav data start")
    with socket(AF_INET, SOCK_DGRAM) as so:
        so.bind((LOCALIP, LOCALPORT))
        while True:
            data = so.recv(1024)
            print(data)


def tacview_socket():
    with socket(AF_INET, SOCK_STREAM, IPPROTO_TCP) as so:
        so.bind((LOCALIP, LOCALPORT))
        so.listen()
        print("Listening for client connections ...")
        ss, addr = so.accept()
        print("Client connected")

        # Send handshake data
        ss.send(HandShakeData1.encode('utf-8'))
        ss.send(HandShakeData2.encode('utf-8'))
        ss.send(HandShakeData3.encode('utf-8'))
        ss.send(b'\x00')

        # Incoming handshake response handling
        data = ss.recv(1024)
        print('Waiting for handshake: ', data)

        # Send the file header and reference time
        ss.send(TelFileHeader.encode('utf-8'))
        current_time = time.strftime(TelReferenceTimeFormat, time.gmtime()).encode('utf-8')
        ss.send(current_time)

        print('Ready to send data')
        return ss


if __name__ == "__main__":
    ss = tacview_socket()  # Start the Tacview socket connection

    # Start a thread to receive messages
    # recv_thread = Thread(target=recv_msg)
    # recv_thread.start()

    server_thread = Thread(target=serverthread, args=(ss,))
    server_thread.start()