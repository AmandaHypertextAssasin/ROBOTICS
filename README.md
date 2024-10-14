# ROBOTICS

THIS IS A REPOSITORY FOR MY FIRST OFFICIAL ROBOTICS PROJECT.ME AND MY CLLEAGUE ARE BUILDING THREE ROBOTS WHO SELECT
A KING AMONG THE THREE OF THEM BY FOLLOWING THIS ALGORITHM:

To create an algorithm for broadcasting a number and electing a "king" among participants, you can use a simple approach inspired by consensus protocols. Here’s a high-level outline of the algorithm:

### Assumptions
1. **Participants**: A group of participants, each identified by a unique ID.
2. **Broadcast Mechanism**: A reliable way for all participants to communicate.
3. **Random Number**: Each participant generates a random number.

### Algorithm Steps

1. **Initialization**:
   - Each participant generates a random number and stores it locally.

2. **Broadcast**:
   - Each participant broadcasts its random number to all other participants.

3. **Collect Numbers**:
   - Each participant collects all the random numbers it receives from others.

4. **Determine the King**:
   - Each participant compares all received numbers (including its own):
     - The participant with the highest number becomes the "king."
     - In case of a tie, use the participant's ID (or any unique identifier) as a tiebreaker; the participant with the highest ID wins.

5. **Announce the King**:
   - The elected king broadcasts its ID to all participants, confirming their role.

6. **Final Confirmation**:
   - Each participant verifies the received ID and acknowledges it. If a participant receives multiple kings (in the case of network delays), it resolves it based on its own local logic (e.g., always trust the first valid announcement).

### Pseudocode

```plaintext
function electKing(participants):
    local_number = generateRandomNumber()
    broadcast(local_number)

    received_numbers = []
    
    for each participant in participants:
        number = waitForBroadcast()
        received_numbers.append(number)

    // Include own number
    received_numbers.append(local_number)

    // Find the king
    king_number = max(received_numbers)
    king_id = findParticipantWithNumber(king_number)

    // Broadcast the king
    broadcast(king_id)

    // Confirmation phase
    waitForConfirmation(king_id)
```

### Notes
- **Reliability**: The algorithm assumes that the broadcasting mechanism is reliable and that all messages eventually reach all participants.
- **Scalability**: For larger groups, we should consider more sophisticated methods to handle message congestion and failures, such as leader election algorithms (e.g., Bully Algorithm or Ring Algorithm).
- **Security**: We must ensure that the random number generation is secure to prevent manipulation.

This algorithm provides a straightforward way to elect a king based on a distributed consensus mechanism.
