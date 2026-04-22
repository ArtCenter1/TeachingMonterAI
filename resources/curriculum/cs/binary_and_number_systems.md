# Binary and Number Systems

In our everyday lives, we use the decimal system (Base 10), which uses ten digits (0-9). However, computers are built from electronic switches (transistors) that can only be in one of two states: ON or OFF. Because of this, computers use the Binary system (Base 2).

## Binary (Base 2)

Binary uses only two digits: 0 and 1. Each digit in a binary number is called a **bit** (short for Binary Digit).
- **Place Values**: In decimal, place values are powers of 10 (1, 10, 100, 1000). In binary, they are powers of 2 (1, 2, 4, 8, 16, 32, 64, 128).
- **Conversion (Binary to Decimal)**: To convert `1011` to decimal, you add the place values where there is a 1: (1 × 8) + (0 × 4) + (1 × 2) + (1 × 1) = 8 + 0 + 2 + 1 = 11.
- **Conversion (Decimal to Binary)**: To convert `13` to binary, you find the largest power of 2 that fits into 13 (which is 8), subtract it, and repeat: 13 - 8 = 5; 5 - 4 = 1; 1 - 1 = 0. So, 13 is `1101` in binary (one 8, one 4, zero 2s, one 1).

## Hexadecimal (Base 16)

Binary numbers can become very long and difficult for humans to read. Hexadecimal (Hex) is a shorthand for binary. It uses 16 digits: 0-9 followed by A-F (where A=10, B=11, C=12, D=13, E=14, F=15).
- **The 4-Bit Connection**: Each hex digit represents exactly four bits (a "nibble"). For example, `F` is `1111` and `A` is `1010`.
- **Use in Computing**: Hex is commonly used for colour codes in web design (e.g., `#FF5733`) and for memory addresses in programming.

## Two's Complement: Representing Negative Numbers

Computers don't have a "+" or "-" sign; they only have bits. To represent negative numbers, we use a system called **Two's Complement**.
- The most significant bit (the leftmost bit) becomes a negative value. In an 8-bit system, the leftmost bit represents -128 instead of +128.
- To make a number negative: flip all the bits (0 to 1, 1 to 0) and then add 1.

## Character Encoding: ASCII and Unicode

How do bits represent letters? We use an encoding standard.
- **ASCII**: An older 7-bit system that can represent 128 characters (English alphabet, numbers, and basic symbols).
- **Unicode**: A modern system that can represent over 140,000 characters, including every language on Earth and even emojis. UTF-8 is the most common version of Unicode used on the web.

## Common Misconceptions

A major misconception is that computers "understand" decimal but just use binary because it's faster. Computers physically cannot understand decimal; the hardware is fundamentally binary. Another error is thinking that Hexadecimal is a "different kind" of data. It's just a way for *humans* to view binary more easily; the computer still sees it as 0s and 1s. Finally, students often forget the "Add 1" step in Two's Complement, which is essential for the math to work correctly.

## Analogy: The Light Switch Array

Imagine a hallway with 8 light switches. Each switch can only be up (1) or down (0). You can't put a switch "halfway" (decimal 5). To represent a number, you have to use a pattern of up and down switches. If you want to communicate with a friend using these switches, you'd both need to agree on what each pattern means (encoding).

## Vocabulary Checklist

Binary · Bit · Byte · Decimal · Hexadecimal · Base · Place value · Two's Complement · ASCII · Unicode · Nibble · Transistor · Encoding · Most Significant Bit · Overflow
