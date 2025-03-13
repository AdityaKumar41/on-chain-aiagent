import React, { useState } from "react";
import { ethers } from "ethers";
import axios from "axios";
import contractABI from "../AIAgent.json";

const contractAddress = "0x314157c8124D4ace0CDC428D18F47E8e6B2b556b";

function App() {
  const [topic, setTopic] = useState("");
  const [taskId, setTaskId] = useState(null);
  const [result, setResult] = useState("");

  const createTask = async () => {
    if (!window.ethereum) return alert("Install MetaMask!");
    const provider = new ethers.providers.Web3Provider(window.ethereum);
    const signer = provider.getSigner();
    const contract = new ethers.Contract(contractAddress, contractABI, signer);

    const tx = await contract.createTask(topic);
    await tx.wait();

    contract.on("TaskCreated", (id, topic) => {
      setTaskId(id.toString());
      axios.post("http://localhost:5000/process_task", {
        task_id: id.toString(),
        topic,
      });
    });
  };

  const fetchResult = async () => {
    if (!taskId) return;
    const provider = new ethers.providers.Web3Provider(window.ethereum);
    const contract = new ethers.Contract(
      contractAddress,
      contractABI,
      provider
    );
    const task = await contract.getTask(taskId);
    setResult(task.result);
  };

  return (
    <div style={{ textAlign: "center", marginTop: "50px" }}>
      <h1>On-Chain AI Agent</h1>
      <input
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        placeholder="Enter topic..."
      />
      <button onClick={createTask}>Submit Task</button>
      <button onClick={fetchResult}>Fetch Result</button>
      {taskId && <p>Task ID: {taskId}</p>}
      {result && <p>Result: {result}</p>}
    </div>
  );
}

export default App;
