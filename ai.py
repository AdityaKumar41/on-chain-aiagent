import os
import json
import time
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from dotenv import load_dotenv
from web3 import Web3
from crewai import Agent, Task, Crew, LLM
import uvicorn
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name=s) - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
AVAX_RPC_URL = os.getenv("AVALANCHE_FUJI_RPC")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# Blockchain content limits
# Ethereum/Avalanche has a limit per transaction. For string data, we need to be conservative
# A string stored in a contract typically costs ~20k gas per KB
BLOCKCHAIN_TEXT_LIMIT = 5000  # Maximum character limit to store on chain
BLOCKCHAIN_TEXT_LIMIT_BYTES = 10240  # ~10KB in bytes
SUMMARY_LENGTH = 100  # Length for summary if content is truncated

# Initialize Web3
web3 = Web3(Web3.HTTPProvider(AVAX_RPC_URL))
account = web3.eth.account.from_key(PRIVATE_KEY)

# Load the contract ABI
ABI_PATH = "AIAgent.json"

if not os.path.exists(ABI_PATH):
    raise FileNotFoundError(f"ABI file {ABI_PATH} not found. Ensure it exists in the project root.")

with open(ABI_PATH, "r") as f:
    contract_abi = json.load(f)

contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)

# Initialize LLM
llm = LLM(model="groq/llama-3.2-90b-vision-preview", api_key=GROQ_API_KEY)

# Define Pydantic models for request/response validation
class TaskRequest(BaseModel):
    task_id: int
    topic: str

class TaskResponse(BaseModel):
    task_id: int
    local_result: str
    transaction_hash: str
    transaction_status: str
    on_chain_result: Optional[Dict[str, Any]]

class ErrorResponse(BaseModel):
    error: str

class BlockchainTask(BaseModel):
    id: int
    topic: str
    result: str
    requester: str

# Function to prepare content for blockchain storage
def prepare_blockchain_content(content: str) -> Dict[str, Any]:
    """
    Prepares content for blockchain storage by checking size limits 
    and formatting if needed.
    
    Returns:
        Dict containing formatted content and metadata
    """
    original_length = len(content)
    byte_size = len(content.encode('utf-8'))
    
    result = {
        "original_length": original_length,
        "original_byte_size": byte_size,
        "truncated": False,
        "content": content
    }
    
    # Check if content exceeds byte limit
    if byte_size > BLOCKCHAIN_TEXT_LIMIT_BYTES:
        # Calculate approximately how many characters we can keep
        # This is approximate as UTF-8 chars can be 1-4 bytes
        approx_ratio = BLOCKCHAIN_TEXT_LIMIT_BYTES / byte_size
        safe_char_limit = int(original_length * approx_ratio * 0.9)  # 10% safety margin
        
        # Ensure we don't exceed character limit
        safe_char_limit = min(safe_char_limit, BLOCKCHAIN_TEXT_LIMIT)
        
        # Truncate content smartly - try to break at paragraph or sentence
        truncated_content = content[:safe_char_limit]
        
        # Try to find natural breakpoints
        last_paragraph = truncated_content.rfind('\n\n')
        last_sentence = truncated_content.rfind('. ')
        
        breakpoint = max(last_paragraph, last_sentence)
        if breakpoint > int(safe_char_limit * 0.8):  # Only use if breakpoint is reasonably far in
            truncated_content = truncated_content[:breakpoint+1]
        
        # Add summary and note about truncation
        summary = content[:SUMMARY_LENGTH] + "..."
        truncation_note = (
            f"\n\n[Content was truncated to fit blockchain storage limits. "
            f"Original length: {original_length} characters / {byte_size} bytes. "
            f"Summary: {summary}]"
        )
        
        final_content = truncated_content + truncation_note
        
        result["content"] = final_content
        result["truncated"] = True
        result["truncated_length"] = len(final_content)
        result["truncated_byte_size"] = len(final_content.encode('utf-8'))
    
    return result

# Function to get task data from blockchain
def get_task_from_blockchain(task_id):
    try:
        task = contract.functions.getTask(task_id).call()
        return {
            "id": task[0],
            "topic": task[1],
            "result": task[2],
            "requester": task[3]
        }
    except Exception as e:
        logger.error(f"Error fetching task {task_id}: {str(e)}")
        return {"error": f"Failed to fetch task: {str(e)}"}

# Function to get recent task events
def get_recent_tasks(count=10):
    try:
        # Get the latest block number
        latest_block = web3.eth.block_number
        
        # Scan for recent task events
        from_block = max(0, latest_block - 5000)  # Look back ~5000 blocks
        
        # Get TaskCreated and TaskCompleted events
        created_events = contract.events.TaskCreated.get_logs(fromBlock=from_block, toBlock='latest')
        completed_events = contract.events.TaskCompleted.get_logs(fromBlock=from_block, toBlock='latest')
        
        # Process the events
        tasks = {}
        
        for event in created_events:
            task_id = event['args']['id']
            tasks[task_id] = {
                "id": task_id,
                "topic": event['args']['topic'],
                "requester": event['args']['requester'],
                "created_block": event['blockNumber'],
                "created_tx": event['transactionHash'].hex(),
                "status": "Created",
                "result": None
            }
        
        for event in completed_events:
            task_id = event['args']['id']
            if task_id in tasks:
                tasks[task_id].update({
                    "status": "Completed",
                    "result": event['args']['result'],
                    "completed_block": event['blockNumber'],
                    "completed_tx": event['transactionHash'].hex()
                })
            else:
                tasks[task_id] = {
                    "id": task_id,
                    "status": "Completed",
                    "result": event['args']['result'],
                    "completed_block": event['blockNumber'],
                    "completed_tx": event['transactionHash'].hex()
                }
        
        # Convert to list and limit to requested count
        task_list = list(tasks.values())
        task_list.sort(key=lambda x: x.get("completed_block", x.get("created_block", 0)), reverse=True)
        
        return task_list[:count]
    except Exception as e:
        return {"error": f"Failed to fetch recent tasks: {str(e)}"}

# Function to safely send transaction to blockchain
def send_blockchain_transaction(function_call, task_id, result_str):
    """
    Safely sends a transaction to the blockchain with proper error handling
    and transaction management.
    """
    try:
        # Prepare content for blockchain storage
        prepared_content = prepare_blockchain_content(result_str)
        result_for_blockchain = prepared_content["content"]
        
        if prepared_content["truncated"]:
            logger.warning(
                f"Result too long for blockchain storage. Original: {prepared_content['original_length']} chars / "
                f"{prepared_content['original_byte_size']} bytes. Truncated to: {prepared_content['truncated_length']} chars / "
                f"{prepared_content['truncated_byte_size']} bytes."
            )
        
        # Update function call with prepared content
        function_call = contract.functions.completeTask(task_id, result_for_blockchain)
        
        # Get latest nonce
        nonce = web3.eth.get_transaction_count(account.address)
        
        # Estimate gas instead of hardcoding
        try:
            gas_estimate = function_call.estimate_gas({
                "from": account.address,
                "nonce": nonce
            })
            gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
        except Exception as e:
            logger.warning(f"Gas estimation failed: {str(e)}. Using default gas limit.")
            gas_limit = 3000000  # Higher default gas limit
            
        # Get current gas price with slight increase for faster confirmation
        gas_price = int(web3.eth.gas_price * 1.1)
        
        # Build transaction
        tx = function_call.build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price
        })
        
        # Sign and send transaction
        signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = web3.to_hex(tx_hash)
        
        logger.info(f"Transaction sent: {tx_hash_hex}")
        
        # Wait for receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        
        if receipt.status == 1:
            logger.info(f"Transaction successful: {tx_hash_hex}")
            time.sleep(2)  # Give blockchain time to update
            # Verify the data was stored correctly
            blockchain_task = get_task_from_blockchain(task_id)
            return {
                "success": True,
                "transaction_hash": tx_hash_hex,
                "receipt": {
                    "status": receipt.status,
                    "gas_used": receipt.gasUsed,
                    "block_number": receipt.blockNumber
                },
                "on_chain_result": blockchain_task,
                "content_truncated": prepared_content["truncated"],
                "original_length": prepared_content["original_length"],
                "stored_length": len(result_for_blockchain)
            }
        else:
            logger.error(f"Transaction failed: {tx_hash_hex}")
            return {
                "success": False,
                "transaction_hash": tx_hash_hex,
                "error": "Transaction failed",
                "receipt": {
                    "status": receipt.status,
                    "gas_used": receipt.gasUsed,
                    "block_number": receipt.blockNumber
                }
            }
    except Exception as e:
        logger.error(f"Error in blockchain transaction: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

app = FastAPI(title="OnChain AI API", description="API for processing AI tasks and storing results on the blockchain")

@app.post("/process_task", response_model=TaskResponse)
async def process_task(task_data: TaskRequest):
    task_id = task_data.task_id
    topic = task_data.topic
    
    logger.info(f"Processing task {task_id} with topic: {topic}")

    try:
        # Define AI Agents
        planner = Agent(
            role="Strategist",
            goal=f"Plan content for {topic}",
            backstory="An experienced strategist analyzing market trends.",
            llm=llm,
            verbose=True
        )

        writer = Agent(
            role="Writer",
            goal=f"Write an engaging post on {topic}",
            backstory="A professional journalist specializing in finance.",
            llm=llm,
            verbose=True
        )

        editor = Agent(
            role="Editor",
            goal="Refine and polish the post",
            backstory="A meticulous editor ensuring clarity and engagement.",
            llm=llm,
            verbose=True
        )

        # Define Tasks
        plan_task = Task(
            description=f"Research and create a plan for {topic}",
            expected_output="Content Plan",
            agent=planner
        )

        write_task = Task(
            description=f"Write a detailed post based on the plan for {topic}",
            expected_output="LinkedIn Post",
            agent=writer
        )

        edit_task = Task(
            description="Edit and refine the post for clarity and engagement",
            expected_output="Final Post",
            agent=editor
        )

        # Assign tasks to Crew
        crew = Crew(
            agents=[planner, writer, editor],
            tasks=[plan_task, write_task, edit_task],
            llm=llm,
            verbose=True
        )

        # Run the Crew tasks
        result = crew.kickoff(inputs={"topic": topic})

        # 🔥 Convert `CrewOutput` to `string`
        if isinstance(result, dict):
            result_str = json.dumps(result)  # Convert dict to JSON string
        elif isinstance(result, list):
            result_str = "\n".join(str(r) for r in result)  # Convert list to string
        else:
            result_str = str(result)  # Ensure it's a plain string

        logger.info(f"AI processing completed, result length: {len(result_str)} characters, "
                   f"{len(result_str.encode('utf-8'))} bytes")

        # Send result to blockchain using the new safe transaction function
        function_call = contract.functions.completeTask(task_id, result_str)
        tx_result = send_blockchain_transaction(function_call, task_id, result_str)
        
        if tx_result["success"]:
            logger.info(f"Task {task_id} completed and stored on blockchain")
            response = {
                "task_id": task_id,
                "local_result": result_str,
                "transaction_hash": tx_result["transaction_hash"],
                "transaction_status": "Successful",
                "on_chain_result": tx_result["on_chain_result"]
            }
            
            # Add content truncation info if applicable
            if tx_result.get("content_truncated", False):
                response["content_status"] = {
                    "truncated": True,
                    "original_length": tx_result["original_length"],
                    "stored_length": tx_result["stored_length"],
                    "percentage_stored": round(tx_result["stored_length"] / tx_result["original_length"] * 100, 2)
                }
                
            return response
        else:
            logger.error(f"Failed to store task {task_id} on blockchain: {tx_result.get('error')}")
            # Return the error but still include the local result
            return {
                "task_id": task_id,
                "local_result": result_str,
                "transaction_hash": tx_result.get("transaction_hash", ""),
                "transaction_status": "Failed",
                "error_details": tx_result.get("error", "Unknown error"),
                "on_chain_result": None
            }

    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# New endpoint to get blockchain storage constraints
@app.get("/blockchain_limits")
async def blockchain_limits():
    """
    Returns information about blockchain storage constraints for AI content
    """
    return {
        "max_text_length": BLOCKCHAIN_TEXT_LIMIT,
        "max_byte_size": BLOCKCHAIN_TEXT_LIMIT_BYTES,
        "notes": [
            "Content exceeding these limits will be automatically truncated",
            "Storing large text on-chain is expensive and may require high gas fees",
            "For very large content, consider storing only a summary on-chain with a link to off-chain storage"
        ],
        "estimated_gas_per_kb": "~20,000 gas",
        "recommendation": "Keep content under 5KB for optimal performance and cost"
    }

@app.get("/get_task/{task_id}", response_model=Union[BlockchainTask, ErrorResponse])
async def get_task(task_id: int):
    try:
        logger.info(f"Fetching task {task_id} from blockchain")
        task = get_task_from_blockchain(task_id)
        
        # Check if we got an error or if result is empty
        if "error" in task:
            logger.warning(f"Error fetching task {task_id}: {task['error']}")
            return JSONResponse(status_code=404, content={"error": task["error"]})
        
        if not task["result"]:
            logger.info(f"Task {task_id} exists but has no result yet")
        
        # Always return the on-chain data
        return task
        
    except Exception as e:
        logger.error(f"Exception fetching task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recent_tasks")
async def recent_tasks(count: int = Query(10, description="Number of recent tasks to fetch")):
    try:
        logger.info(f"Fetching {count} recent tasks")
        tasks = get_recent_tasks(count)
        return tasks
    except Exception as e:
        logger.error(f"Error fetching recent tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Root endpoint for API documentation info
@app.get("/")
async def root():
    return {"message": "Welcome to OnChain AI API. Visit /docs for API documentation"}

# Endpoint to fetch final on-chain content for a task
@app.get("/task_result/{task_id}")
async def task_result(task_id: int):
    """
    Fetches the final on-chain content for a specific task.
    This endpoint focuses only on retrieving the stored result.
    """
    try:
        logger.info(f"Fetching final result for task {task_id}")
        task = get_task_from_blockchain(task_id)
        
        if "error" in task:
            return JSONResponse(status_code=404, content={"error": task["error"]})
            
        # Return just the result from the on-chain task
        return {
            "task_id": task["id"],
            "topic": task["topic"],
            "result": task["result"],
            "requester": task["requester"]
        }
    except Exception as e:
        logger.error(f"Error fetching task result {task_id}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    logger.info(f"Starting OnChain AI API server on port 5000")
    uvicorn.run("ai:app", host="0.0.0.0", port=5000, reload=True)
