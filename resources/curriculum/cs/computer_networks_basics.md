# Computer Networks Basics

A computer network is a collection of computers and other hardware components interconnected by communication channels that allow sharing of resources and information. The largest and most famous network is the Internet.

## The OSI Model: Layers of Communication

To manage the complexity of networking, we use a 7-layer model called the OSI (Open Systems Interconnection) model. Each layer has a specific job:
1. **Physical**: The actual wires, radio waves, or fibre optics.
2. **Data Link**: Organising bits into "frames" and managing physical addresses (MAC addresses).
3. **Network**: Routing data between different networks using IP addresses.
4. **Transport**: Ensuring data arrives correctly (TCP) or quickly (UDP).
5. **Session**: Managing the "conversation" between two devices.
6. **Presentation**: Translating data into a readable format (encryption, compression).
7. **Application**: The software you interact with (HTTP for web, SMTP for email).

## IP Addresses and DNS

Every device on a network needs a unique address.
- **IP Address**: A numerical label. IPv4 (e.g., `192.168.1.1`) is the older standard; IPv6 (e.g., `2001:0db8...`) was created because we ran out of IPv4 addresses.
- **DNS (Domain Name System)**: Humans are bad at remembering numbers but good at remembering names. DNS is the "phonebook of the internet" that translates `google.com` into an IP address.

## Protocols: The Rules of the Road

A protocol is a set of rules that governs how data is exchanged.
- **TCP (Transmission Control Protocol)**: Reliable. It checks that every packet arrived and puts them back in the right order. Used for web and email.
- **UDP (User Datagram Protocol)**: Fast but unreliable. It just sends data and doesn't check if it arrived. Used for video calls and online gaming.
- **HTTP/HTTPS**: The protocol for the World Wide Web. The 'S' stands for Secure (encrypted).

## Network Topology and Hardware

- **LAN (Local Area Network)**: A network in a small area like a home or office.
- **WAN (Wide Area Network)**: A network covering a large geographic area (the Internet is a WAN).
- **Router**: A device that directs data packets between different networks.
- **Switch**: A device that connects devices within a single LAN.

## Common Misconceptions

The most common misconception is that "The Internet" and "The World Wide Web" are the same thing. The Internet is the infrastructure (the pipes and wires); the Web is just one service that runs on top of it. Another error is thinking that data travels in a straight line from source to destination. In reality, a single email is broken into many "packets" that might take completely different paths across the globe before being reassembled at the end. Finally, many believe that "incognito mode" makes them invisible on a network. It doesn't; it only prevents your own browser from saving your history locally.

## Analogy: Sending a Book via Post

Imagine you want to send a 500-page book to a friend, but the post office only accepts envelopes that hold 1 page.
1. You tear out every page (Packetization).
2. You write the destination address and a page number on every envelope (IP Addressing and Sequencing).
3. You drop them in the mail. They might go on different trucks or planes (Routing).
4. Your friend receives them. If page 42 is missing, they send you a note asking for it again (TCP Reliability).
5. Once they have all the pages, they put them back in order and read the book (Reassembly).

## Vocabulary Checklist

Protocol · IP Address · DNS · Packet · Router · Switch · LAN · WAN · TCP · UDP · HTTP · OSI Model · MAC Address · Bandwidth · Latency
