# 🤖 On-Chain AI Agent

A powerful AI agent system that processes AI tasks and stores results directly on the blockchain, creating permanent, verifiable, and decentralized AI-generated content.

![On-Chain AI Agent](https://via.placeholder.com/800x400?text=On-Chain+AI+Agent)

## 📋 Overview

This project combines the power of AI with blockchain technology to create an autonomous AI agent that:

1. Receives task instructions from blockchain events
2. Processes content generation tasks using a multi-agent AI system
3. Stores the generated content permanently on-chain
4. Provides API access to interact with the system

The on-chain AI agent operates with a crew of specialized AI agents (Strategist, Writer, and Editor) that collaborate to produce high-quality content based on given topics.

## ⚙️ Technical Stack

- **Blockchain**: Avalanche Fuji Testnet
- **Smart Contract**: Solidity-based AIAgent
- **AI Framework**: CrewAI with Groq LLM
- **Backend**: FastAPI
- **Web3 Integration**: web3.py

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js and npm
- Avalanche Fuji testnet access
- Groq API key

### Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd on-chain-ai
   ```

2. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with the following variables:

   ```
   GROQ_API_KEY=your_groq_api_key
   AVALANCHE_FUJI_RPC=https://api.avax-test.network/ext/bc/C/rpc
   CONTRACT_ADDRESS=your_deployed_contract_address
   PRIVATE_KEY=your_wallet_private_key
   ```

4. Start the API server:
   ```bash
   python ai.py
   ```

## 🖥️ User Interface Guide

### Web Interface

Visit `http://localhost:5000/docs` after starting the server to access the interactive API documentation.

### API Endpoints

#### 1. Create and Process a Task

**Endpoint**: POST `/process_task`

**Request Body**:

```json
{
  "task_id": 1,
  "topic": "Web3 Integration with AI Systems"
}
```

**Response**:

```json
{
  "task_id": 1,
  "local_result": "Generated content...",
  "transaction_hash": "0x...",
  "transaction_status": "Successful",
  "on_chain_result": {
    "id": 1,
    "topic": "Web3 Integration with AI Systems",
    "result": "Generated content...",
    "requester": "0x..."
  }
}
```

#### 2. Retrieve a Task from Blockchain

**Endpoint**: GET `/get_task/{task_id}`

**Response**:

```json
{
  "id": 1,
  "topic": "Web3 Integration with AI Systems",
  "result": "Generated content stored on blockchain...",
  "requester": "0x..."
}
```

#### 3. Get Recent Tasks

**Endpoint**: GET `/recent_tasks?count=5`

Returns a list of the most recent tasks processed by the system.

#### 4. Get Blockchain Storage Limits

**Endpoint**: GET `/blockchain_limits`

Returns information about content size limitations for blockchain storage.

#### 5. Get Task Result

**Endpoint**: GET `/task_result/{task_id}`

Returns only the final result content from the blockchain.

## 📱 Example UI Workflow

1. **Submit a New Task**:

   - Create a task ID and topic
   - Submit to the `/process_task` endpoint
   - The system will process the request through multiple AI agents

2. **Monitor Processing**:

   - The API provides real-time feedback on the processing status
   - You can view logs of the AI agents collaborating

3. **View Results**:

   - Once processing is complete, the content is stored on blockchain
   - Access the result using the `/get_task/{task_id}` or `/task_result/{task_id}` endpoint

4. **Verify On-Chain**:
   - Use the transaction hash to verify the content on Avalanche Fuji explorer
   - The content is permanently stored and immutable

## ⚠️ Content Size Limitations

When storing content on-chain, be aware of size limitations:

- Maximum recommended text length: 5,000 characters
- Maximum byte size: ~10KB
- Content exceeding these limits will be automatically truncated
- For large content, consider storing a summary on-chain with a link to off-chain storage

## 🔄 Project Structure

```
on-chain-ai/
│
├── ai.py                # Main FastAPI server and AI logic
├── AIAgent.json         # Smart contract ABI
├── .env                 # Environment variables (create this)
├── README.md            # This documentation
└── requirements.txt     # Python dependencies
```

## 🛠️ Customization

### Modifying AI Agents

You can customize the AI agents in `ai.py` by changing their roles, goals, and backstories:

```python
planner = Agent(
    role="Your Custom Role",
    goal="Your Custom Goal",
    backstory="Your Custom Backstory",
    llm=llm,
    verbose=True
)
```

### Smart Contract Integration

To integrate with your own smart contract:

1. Deploy the AIAgent smart contract to Avalanche Fuji testnet
2. Update the CONTRACT_ADDRESS in your .env file
3. Ensure your wallet has sufficient AVAX for gas fees

## 📈 Future Improvements

- Web-based UI for easier interaction
- Support for multiple LLM providers
- Integration with decentralized storage (IPFS) for large content
- Multi-chain support beyond Avalanche

## 📄 License

[Specify your license here]

## 👥 Contact

[Your contact information]
