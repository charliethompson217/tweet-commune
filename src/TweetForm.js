import React, { useState, useEffect } from 'react';
import { post } from 'aws-amplify/api';
import { Amplify } from 'aws-amplify';
import awsExports from './aws-exports';
Amplify.configure(awsExports);

const TweetForm = () => {
    const [tweet, setTweet] = useState("");
    const [file, setFile] = useState(null);
    const [isValid, setIsValid] = useState(true);
    const [warning, setWarning] = useState("");
    const [info, setInfo] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [inputKey, setInputKey] = useState(Date.now());

    useEffect(() => {
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif'];
        if (file && !allowedTypes.includes(file.type)) {
            setWarning("File must be a JPEG, PNG, or GIF");
            setIsValid(false);
        } 
        else if (tweet.length > 280) {
            setWarning("Tweets must be less than 280 characters");
            setIsValid(false);
        } else if (tweet.length > 0) {
            setWarning("");
            setInfo("");
            setIsValid(true);
        }
    }, [tweet, file]);

    async function submitText(data) {
        try {
            const restOperation = post({
                apiName: 'twitterAPI',
                path: '/tweet/text',
                options: {
                    body: {
                        message: data,
                    },
                },
            });
            const { body } = await restOperation.response;
            const response = await body.json();
            if (response.error) {
                console.error('Error Submiting Text: ', response.error);
                setWarning(response.error);
            } else {
                setInfo("Tweet Submited Successfully!");
            }
        } catch (e) {
            console.error('Error Submiting Text: ', e);
            setWarning('Error Submiting Tweet');
        }
    }

    async function requestUploadURL(textData, key, contentType) {
        try {
            const restOperation = post({
                apiName: 'twitterAPI',
                path: `/tweet/getUploadLink?objectName=${key}&contentType=${encodeURIComponent(contentType)}`,
                options: {
                    body: {
                        message: textData,
                    },
                },
            });
            const { body } = await restOperation.response;
            const response = await body.json();
            if (response.error) {
                console.error('Error Requesting Upload URL: ', response.error);
                setWarning(response.error);
                return;
            }
            const presignedUrl = response.url;
            return presignedUrl;
        } catch (e) {
            console.error('Error Requesting Upload URL: ', e);
            setWarning('Error Submiting Tweet');
        }
    }

    async function uploadImage(presignedUrl, contentType, textData, imageData) {
        try {
            const response = await fetch(presignedUrl, {
                method: 'PUT',
                headers: {
                    'Content-Type': contentType,
                    'x-amz-meta-tweet-text': textData,
                },
                body: imageData,
            });
            if (response.ok) {
                setTweet('');
                setFile(null);
                setInputKey(Date.now());
                setInfo("Tweet Submited Successfully!");
            } else {
                console.error('Error Uploading Image: ', response.statusText);
                setWarning('Error Submiting Tweet');
            }
        } catch (error) {
            console.error('Error Uploading Image', error);
            setWarning('Error Submiting Tweet');
        }
    }

    async function sendTweet() {
        const data = tweet;
        try {
            if (!isValid) {
                return;
            }
            if (file) {
                setIsLoading(true);
                const key = inputKey;
                const imageData = file;
                const contentType = imageData.type;
                const url = await requestUploadURL(data, key, contentType);
                await uploadImage(url, contentType, data, imageData);
            } else {
                if (!data.trim()) {
                    setWarning("Tweet cannot be empty");
                    return;
                }
                setIsLoading(true);
                await submitText(data);
                setTweet('');
            }
        } catch (e) {
            console.error('Error Submiting Tweet: ', e);
            setWarning('Error Submiting Tweet');
        }
        setIsLoading(false);
    }

    return (
        <div className='tweet-form'>
            <h1>Tweet Something</h1>
            <textarea
                value={tweet}
                onChange={(e) => setTweet(e.target.value)}
                placeholder="What's happening?"
                className="tweet-textarea"
            />
            <div>
                <input
                    key={inputKey}
                    type="file"
                    accept="image/jpeg, image/png, image/gif"
                    onChange={(e) => setFile(e.target.files[0])}
                    className="file-input"
                />
            </div>
            <button onClick={sendTweet} className="send-tweet-button">
                Send Tweet
            </button>
            {warning && <p className='warning'>{warning}</p>}
            {info && <p className='info'>{info}</p>}
            {isLoading && <p className="loading">Loading...</p>}
        </div>
    );
};

export default TweetForm;
