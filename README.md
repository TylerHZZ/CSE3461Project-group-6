# CSE 3461 Project1

## Project Overview

This project is developed for **CSE 3461: Computer Networking and Internet Technologies**.

The goal of the project is to build a multi-client chat application using socket programming. The application will support broadcast communication, private one-to-one messaging, and an additional networking-related feature.

## Team Members

- Luca Sivilotti
- Tianrun Lin
- Aaditya Gupta
- Tyler Zhuangzhuang He

## Team Roles

- **Luca Sivilotti** — Feature 
- **Tianrun Lin** — Feature 
- **Aaditya Gupta** — Feature 
- **Tyler Zhuangzhuang He** — Integration, Debugging, Localhost Testing, and Over-the-Air Testing

## Features

### Feature 1 — Broadcast Communication

A client can send a message to the server, and the server forwards the message to all other connected clients.

The server will support multiple clients using threading.

### Feature 2 — One-to-One Private Messaging

Clients will have usernames.

A client can send a private message using the format:

```text
@username message
```

The server will deliver the message only to the specified client.

### Feature 3 — Networking Enhancement

An additional networking-related feature will be implemented.

The feature will include measurable networking results such as:

- Message delay
- Delivery success rate
- Retransmissions
- Messages per second
- Other relevant performance metrics

The final Feature 3 design is currently under development.

## Testing

The project will be tested in two environments:

### Simulation Mode

Multiple clients and the server will run locally using `localhost`.

### Over-the-Air Mode

The server and clients will run on different devices connected through a real network.

## Project Structure



## Development Workflow

Each team member will work on a separate Git branch.

Example branches:

```text
feature/broadcast
feature/private-message
feature/network-enhancement
feature/integration-testing
```

Completed features will be reviewed and merged into the `main` branch.

## Running the Application

Instructions for running the server and clients will be added as development progresses.

Example:

```bash
python server.py
```

In another terminal:

```bash
python client.py
```

## Contributions

Detailed contributions from each team member will be documented in `CONTRIBUTIONS.md`.

## Course

**CSE 3461 — Computer Networking and Internet Technologies**

The Ohio State University  
Autumn 2026
