import React from 'react'

function App() {
  return (
    <div className="flex h-screen w-screen bg-black text-white">
      <div className="w-2/3 border-r border-gray-800">
        {/* 3D Canvas will go here */}
        <div className="flex h-full items-center justify-center">
          <p className="text-xl italic">3D Observatory (React Three Fiber)</p>
        </div>
      </div>
      <div className="w-1/3 p-8 overflow-y-auto">
        <h1 className="text-3xl font-bold mb-4">Perspectiverse</h1>
        <p className="text-gray-400">Select a planet to begin exploring the discourse.</p>
      </div>
    </div>
  )
}

export default App
