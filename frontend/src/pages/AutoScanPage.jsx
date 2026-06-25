import React, { useState, useRef } from "react";
import { startAutoScan } from "../api";

const AutoScanPage = () => {
  const [brandName, setBrandName] = useState("");
  const [isScanning, setIsScanning] = useState(false);
  const [progress, setProgress] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const eventSourceRef = useRef(null);

  const handleStartScan = () => {
    if (!brandName.trim()) {
      alert("Please enter a brand name.");
      return;
    }

    setIsScanning(true);
    setProgress([]);
    setCandidates([]);

    const es = startAutoScan(brandName);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("SSE update:", data);

        // Add progress message
        setProgress((prev) => [...prev, data.message || data.step]);

        if (data.step === "complete" && data.candidates) {
          setCandidates(data.candidates);
          setIsScanning(false);
          es.close();
        }
        if (data.step === "error") {
          setIsScanning(false);
          es.close();
          alert("Scan failed: " + data.message);
        }
      } catch (err) {
        console.error("Failed to parse SSE message:", err);
      }
    };

    es.onerror = (err) => {
      console.error("SSE error:", err);
      setIsScanning(false);
      es.close();
      alert("Connection lost or scan failed. Please try again.");
    };
  };

  const handleStopScan = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsScanning(false);
  };

  return (
    <div className="max-w-4xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">🔍 Auto Scan – Find Job Seekers</h1>
      <p className="text-gray-600 mb-4">
        Automatically discover Telegram groups, scrape messages, and identify people looking for affiliate or promoter jobs.
      </p>

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={brandName}
          onChange={(e) => setBrandName(e.target.value)}
          placeholder="Enter brand name (e.g., ACE2KING)"
          className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          disabled={isScanning}
        />
        {!isScanning ? (
          <button
            onClick={handleStartScan}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            Start Scan
          </button>
        ) : (
          <button
            onClick={handleStopScan}
            className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Stop
          </button>
        )}
      </div>

      {/* Progress Log */}
      {progress.length > 0 && (
        <div className="bg-gray-50 border rounded-lg p-4 mb-6 max-h-60 overflow-y-auto">
          <h3 className="font-semibold text-sm text-gray-600 mb-2">Progress</h3>
          {progress.map((msg, idx) => (
            <div key={idx} className="text-sm text-gray-700 py-1 border-b border-gray-100">
              • {msg}
            </div>
          ))}
        </div>
      )}

      {/* Candidates */}
      {candidates.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-3">🎯 Found {candidates.length} Candidates</h2>
          <div className="grid gap-3">
            {candidates.map((c, idx) => (
              <div key={idx} className="border rounded-lg p-4 bg-white shadow-sm">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium">
                      {c.display_name || "Unknown"} <span className="text-sm text-gray-500">{c.username}</span>
                    </p>
                    <p className="text-sm text-gray-600 mt-1">{c.sample_message}</p>
                    <p className="text-xs text-gray-500 mt-1">Reason: {c.reason}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-semibold">
                      Score: {c.score}/10
                    </span>
                    {c.is_indian_likely && (
                      <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">
                        🇮🇳 Indian
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {isScanning && (
        <div className="mt-4 flex items-center gap-2 text-blue-600">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
          <span>Scanning in progress...</span>
        </div>
      )}
    </div>
  );
};

export default AutoScanPage;
