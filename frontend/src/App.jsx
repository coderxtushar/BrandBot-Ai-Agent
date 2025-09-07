import React, { useState } from 'react';

function App() {
  const [formData, setFormData] = useState({
    target_audience: '',
    expertise: '',
    tone_of_voice: '',
    content_pillars: '',
    linkedin_url: 'https://www.linkedin.com/in/example-user'
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prevState => ({ ...prevState, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setResults(null);
    try {
      const response = await fetch('http://localhost:8000/run-workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError('Failed to get a response from the AI agent. Is the backend server running?');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-gray-50 min-h-screen font-sans">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto py-6 px-4">
          <h1 className="text-3xl font-bold text-center text-blue-600">Autonomous LinkedIn AI Agent</h1>
          <p className="text-center text-gray-500 mt-1">Powered by FastAPI & React with Tailwind CSS</p>
        </div>
      </header>
      <main className="py-10">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8 px-4">
          
          {/* FORM CONTAINER */}
          <div className="bg-white p-8 rounded-lg shadow-md">
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Step 1: Define Your Brand</h2>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label htmlFor="target_audience" className="block text-sm font-medium text-gray-700">Target Audience</label>
                <input type="text" name="target_audience" id="target_audience" className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" value={formData.target_audience} onChange={handleChange} required />
              </div>
              <div>
                <label htmlFor="expertise" className="block text-sm font-medium text-gray-700">Areas of Expertise</label>
                <input type="text" name="expertise" id="expertise" className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" value={formData.expertise} onChange={handleChange} required />
              </div>
              <div>
                <label htmlFor="tone_of_voice" className="block text-sm font-medium text-gray-700">Desired Tone of Voice</label>
                <textarea name="tone_of_voice" id="tone_of_voice" rows="3" className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" value={formData.tone_of_voice} onChange={handleChange} required />
              </div>
              <div>
                <label htmlFor="content_pillars" className="block text-sm font-medium text-gray-700">Content Pillars (comma-separated)</label>
                <textarea name="content_pillars" id="content_pillars" rows="3" className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" value={formData.content_pillars} onChange={handleChange} required />
              </div>
              <div>
                <label htmlFor="linkedin_url" className="block text-sm font-medium text-gray-700">LinkedIn Profile URL</label>
                <input type="url" name="linkedin_url" id="linkedin_url" className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" value={formData.linkedin_url} onChange={handleChange} required />
              </div>
              <button type="submit" disabled={isLoading} className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed">
                {isLoading ? '🤖 AI Workflow in Progress...' : 'Run Full AI Workflow'}
              </button>
            </form>
          </div>
          
          {/* RESULTS CONTAINER */}
          <div className="bg-white p-8 rounded-lg shadow-md">
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Step 2: Review Your Results</h2>
            {isLoading && (
              <div className="flex justify-center items-center h-full">
                <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500"></div>
              </div>
            )}
            {error && <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">{error}</div>}
            {results && (
              <div className="space-y-4">
                <h3 className="text-xl font-semibold text-blue-600">✍️ Your Approved LinkedIn Posts</h3>
                <div className="space-y-6">
                  {results.reviewed_posts.split('---').map((post, index) => (
                    <div key={index} className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                      <pre className="whitespace-pre-wrap font-sans text-gray-800">{post.trim()}</pre>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;